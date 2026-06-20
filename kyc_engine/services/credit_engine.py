"""
AI Credit Underwriting Engine — Phase 2

XGBoost classifier trained on synthetic Indian loan applicant data.
SHAP values provide RBI-mandated explainability for every decision.

Production upgrade path:
  - Replace synthetic training data with historical approved/rejected loan data
  - Add bureau score (CIBIL/Experian) as a feature
  - Retrain quarterly with monitored drift detection
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_model = None
_explainer = None

_FEATURE_NAMES = [
    "monthly_income",
    "monthly_expenses",
    "existing_emis",
    "savings_rate",
    "debt_to_income",
    "emi_to_income",
    "loan_to_annual_income",
    "proposed_emi",
    "net_monthly_surplus",
    "employment_type_encoded",
    "years_employed",
]

_FEATURE_LABELS = {
    "monthly_income":          "Monthly Income",
    "savings_rate":            "Savings Rate",
    "debt_to_income":          "Debt-to-Income Ratio",
    "net_monthly_surplus":     "Net Monthly Surplus",
    "existing_emis":           "Existing EMI Obligations",
    "years_employed":          "Employment Stability",
    "proposed_emi":            "Proposed EMI",
    "loan_to_annual_income":   "Loan-to-Income Ratio",
    "employment_type_encoded": "Employment Type",
    "monthly_expenses":        "Monthly Expenses",
    "emi_to_income":           "EMI-to-Income Ratio",
}


# ── Input / Output schemas ────────────────────────────────────────────────────

@dataclass
class CreditInput:
    applicant_id: str
    monthly_income: float
    monthly_expenses: float
    existing_emis: float
    loan_amount_requested: float
    loan_tenure_months: int
    employment_type: str        # salaried | self_employed | business
    years_employed: float
    kyc_request_id: Optional[str] = None


@dataclass
class CreditDecision:
    credit_score: int           # 300–900 (CIBIL-like scale)
    decision: str               # APPROVE | REVIEW | REJECT
    max_loan_eligible: float
    proposed_emi: float
    interest_rate_band: str
    top_positive_factors: list = field(default_factory=list)
    top_negative_factors: list = field(default_factory=list)
    features_used: dict = field(default_factory=dict)
    shap_values: dict = field(default_factory=dict)
    model_version: str = "xgboost-demo-v1.0"


# ── Feature engineering ───────────────────────────────────────────────────────

def _encode_employment(emp_type: str) -> float:
    return {"salaried": 1.0, "self_employed": 0.75, "business": 0.85}.get(
        emp_type.lower(), 0.60
    )


def _calculate_emi(principal: float, annual_rate: float, months: int) -> float:
    r = annual_rate / 12.0
    if r == 0 or months == 0:
        return principal / max(months, 1)
    return principal * r * (1 + r) ** months / ((1 + r) ** months - 1)


def _build_features(inp: CreditInput) -> dict:
    proposed_emi = _calculate_emi(inp.loan_amount_requested, 0.11, inp.loan_tenure_months)
    total_obligations = inp.existing_emis + proposed_emi
    net_surplus = inp.monthly_income - inp.monthly_expenses - total_obligations

    return {
        "monthly_income":          inp.monthly_income,
        "monthly_expenses":        inp.monthly_expenses,
        "existing_emis":           inp.existing_emis,
        "savings_rate":            max(0.0, (inp.monthly_income - inp.monthly_expenses - inp.existing_emis) / max(inp.monthly_income, 1)),
        "debt_to_income":          total_obligations / max(inp.monthly_income, 1),
        "emi_to_income":           inp.existing_emis / max(inp.monthly_income, 1),
        "loan_to_annual_income":   inp.loan_amount_requested / max(inp.monthly_income * 12, 1),
        "proposed_emi":            proposed_emi,
        "net_monthly_surplus":     net_surplus,
        "employment_type_encoded": _encode_employment(inp.employment_type),
        "years_employed":          inp.years_employed,
    }


# ── Synthetic training data ───────────────────────────────────────────────────

def _generate_training_data(n: int = 6000) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    records = []

    for _ in range(n):
        income       = float(rng.lognormal(10.9, 0.55))   # median ~54k
        expenses     = income * rng.uniform(0.30, 0.75)
        existing_emi = income * rng.uniform(0.00, 0.28)
        loan_amt     = income * rng.uniform(3, 28)
        tenure       = int(rng.choice([12, 24, 36, 48, 60]))
        emp_type     = rng.choice(["salaried", "self_employed", "business"], p=[0.60, 0.25, 0.15])
        yrs_emp      = float(rng.exponential(4.0))

        proposed_emi     = _calculate_emi(loan_amt, 0.11, tenure)
        total_obligation = existing_emi + proposed_emi
        dti              = total_obligation / max(income, 1)
        savings_rate     = max(0.0, (income - expenses - existing_emi) / max(income, 1))
        net_surplus      = income - expenses - total_obligation

        # Rule-based approval probability (mimics real credit policy)
        p = 0.80
        if dti > 0.50:        p *= 0.15
        elif dti > 0.40:      p *= 0.45
        if savings_rate < 0.10: p *= 0.30
        if income < 20_000:   p *= 0.25
        if yrs_emp < 0.5:     p *= 0.35
        if emp_type == "self_employed": p *= 0.85
        if net_surplus < 5_000:  p *= 0.20
        elif net_surplus > 25_000: p = min(p * 1.40, 0.97)

        label = int(rng.random() < min(p, 0.97))

        records.append({
            "monthly_income":          income,
            "monthly_expenses":        expenses,
            "existing_emis":           existing_emi,
            "savings_rate":            savings_rate,
            "debt_to_income":          dti,
            "emi_to_income":           existing_emi / max(income, 1),
            "loan_to_annual_income":   loan_amt / max(income * 12, 1),
            "proposed_emi":            proposed_emi,
            "net_monthly_surplus":     net_surplus,
            "employment_type_encoded": _encode_employment(emp_type),
            "years_employed":          yrs_emp,
            "approved":                label,
        })

    return pd.DataFrame(records)


# ── Model lifecycle ───────────────────────────────────────────────────────────

def _get_model():
    global _model, _explainer
    if _model is not None:
        return _model, _explainer

    import shap
    import xgboost as xgb

    logger.info("Training demo credit model on synthetic data (first request only)…")
    df = _generate_training_data(6000)
    X = df[_FEATURE_NAMES]
    y = df["approved"]

    _model = xgb.XGBClassifier(
        n_estimators=150,
        max_depth=4,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        eval_metric="logloss",
        verbosity=0,
    )
    _model.fit(X, y)
    _explainer = shap.TreeExplainer(_model)
    logger.info("Credit model ready.")
    return _model, _explainer


# ── Score → CIBIL range ───────────────────────────────────────────────────────

def _prob_to_cibil(prob: float) -> int:
    return int(300 + prob * 600)


def _score_to_rate(score: int) -> str:
    if score >= 800: return "8.50–9.50%"
    if score >= 750: return "9.50–10.50%"
    if score >= 700: return "10.50–11.50%"
    if score >= 650: return "11.50–13.00%"
    return "13.00–16.00%"


def _max_eligible_loan(monthly_income: float, existing_emis: float, tenure_months: int) -> float:
    """Max loan where total EMI ≤ 40% of income (standard FOIR policy)."""
    max_emi = monthly_income * 0.40 - existing_emis
    if max_emi <= 0:
        return 0.0
    r = 0.11 / 12.0
    n = tenure_months
    return max_emi * ((1 + r) ** n - 1) / (r * (1 + r) ** n)


# ── Public API ────────────────────────────────────────────────────────────────

def assess_credit(inp: CreditInput) -> CreditDecision:
    model, explainer = _get_model()

    features = _build_features(inp)
    X = pd.DataFrame([features])[_FEATURE_NAMES]

    prob = float(model.predict_proba(X)[0][1])
    score = _prob_to_cibil(prob)

    decision = "APPROVE" if score >= 700 else ("REVIEW" if score >= 600 else "REJECT")

    # SHAP — handle both old list API and new Explanation API
    raw_shap = explainer.shap_values(X)
    if isinstance(raw_shap, list):
        sv = raw_shap[1][0]        # binary: index 1 = positive class, row 0
    else:
        sv = np.array(raw_shap)[0] # newer shap returns ndarray directly

    shap_map = dict(zip(_FEATURE_NAMES, sv.tolist()))
    ranked   = sorted(shap_map.items(), key=lambda x: abs(x[1]), reverse=True)

    top_positive = [
        {"factor": _FEATURE_LABELS.get(k, k), "impact": round(v, 4)}
        for k, v in ranked if v > 0
    ][:3]
    top_negative = [
        {"factor": _FEATURE_LABELS.get(k, k), "impact": round(v, 4)}
        for k, v in ranked if v < 0
    ][:3]

    proposed_emi = features["proposed_emi"]
    max_loan = _max_eligible_loan(inp.monthly_income, inp.existing_emis, inp.loan_tenure_months)

    return CreditDecision(
        credit_score=score,
        decision=decision,
        max_loan_eligible=round(max_loan),
        proposed_emi=round(proposed_emi),
        interest_rate_band=_score_to_rate(score),
        top_positive_factors=top_positive,
        top_negative_factors=top_negative,
        features_used={k: round(v, 2) if isinstance(v, float) else v for k, v in features.items()},
        shap_values={_FEATURE_LABELS.get(k, k): round(v, 4) for k, v in shap_map.items()},
    )

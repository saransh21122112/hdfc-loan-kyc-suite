"""
AML Compliance Monitor — Phase 3

Two-layer detection:
  Layer 1 — Isolation Forest (ML): learns what "normal" transaction patterns look like
             and scores how anomalous the applicant's behaviour is.
  Layer 2 — Rule engine: PMLA-specific flags (structuring, velocity, dormancy revival).

Both layers run on every loan applicant as a PMLA §12 obligation.
Final risk level: LOW / MEDIUM / HIGH / CRITICAL

RBI / PMLA references:
  - PMLA 2002, §12: reporting obligations for cash transactions > ₹10L
  - RBI Master Direction on KYC (2016, updated 2023): STR/CTR thresholds
  - Structuring threshold: ₹50,000 (transactions split to stay below)
"""

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

_iso_model = None  # Lazy-trained Isolation Forest

# ── Input schema ──────────────────────────────────────────────────────────────

@dataclass
class TransactionProfile:
    applicant_id: str

    # Volume
    total_transactions_90d: int       # total txns in last 90 days
    total_credits_90d: float          # total INR credited
    total_debits_90d: float           # total INR debited

    # Cash patterns
    cash_deposits_count: int          # number of cash deposit txns
    cash_deposit_total: float         # total cash deposited (INR)

    # Structuring signals
    txns_just_below_50k: int          # count of txns between ₹45k–₹49,999
    txns_just_below_10l: int          # count of txns between ₹9L–₹9,99,999

    # Velocity
    largest_single_txn: float         # largest single transaction (INR)
    round_number_txns: int            # txns that are exact round numbers (10k, 25k, 50k)
    international_txns: int           # cross-border transactions

    # Account behaviour
    account_age_months: int           # how old the account is
    dormancy_months: int              # months account was dormant before activity
    peak_balance: float               # highest balance observed in period


# ── Output schema ─────────────────────────────────────────────────────────────

@dataclass
class AMLFlag:
    code: str
    severity: str       # LOW | MEDIUM | HIGH | CRITICAL
    description: str
    pmla_reference: str


@dataclass
class AMLResult:
    applicant_id: str
    anomaly_score: float            # 0–100 (100 = most anomalous)
    risk_level: str                 # LOW | MEDIUM | HIGH | CRITICAL
    flags: List[AMLFlag] = field(default_factory=list)
    ml_isolation_score: float = 0.0
    rule_flags_triggered: int = 0
    pmla_sar_required: bool = False
    pmla_ctr_required: bool = False
    audit_summary: str = ""
    model_version: str = "isolation-forest-demo-v1.0"


# ── Feature extraction ────────────────────────────────────────────────────────

def _extract_features(p: TransactionProfile) -> np.ndarray:
    safe_txns = max(p.total_transactions_90d, 1)
    safe_credits = max(p.total_credits_90d, 1)

    return np.array([
        p.total_transactions_90d,
        p.total_credits_90d,
        p.total_debits_90d,
        p.cash_deposits_count / safe_txns,                     # cash deposit ratio
        p.cash_deposit_total / safe_credits,                   # cash as % of income
        p.txns_just_below_50k,
        p.txns_just_below_10l,
        p.largest_single_txn,
        p.round_number_txns / safe_txns,                       # round-number ratio
        p.international_txns,
        min(p.account_age_months, 120),
        p.dormancy_months,
        abs(p.total_credits_90d - p.total_debits_90d) / safe_credits,  # imbalance ratio
    ])


# ── Synthetic training data ───────────────────────────────────────────────────

def _generate_normal_profiles(n: int = 4000) -> np.ndarray:
    """Simulates clean, legitimate Indian salary/business account patterns."""
    rng = np.random.default_rng(42)
    rows = []
    for _ in range(n):
        income = rng.lognormal(10.9, 0.55)
        txns   = int(rng.integers(8, 60))
        credits = income * rng.uniform(0.9, 1.1)
        debits  = credits * rng.uniform(0.60, 0.95)
        rows.append([
            txns,
            credits,
            debits,
            rng.uniform(0, 0.15),               # cash ratio
            rng.uniform(0, 0.20),               # cash % of income
            int(rng.integers(0, 2)),             # structuring (rare)
            0,                                   # no 10L structuring
            credits * rng.uniform(0.05, 0.40),  # largest txn
            rng.uniform(0.05, 0.35),            # round number ratio
            int(rng.integers(0, 3)),             # international
            int(rng.integers(12, 120)),          # account age
            0,                                   # no dormancy
            rng.uniform(0.02, 0.30),            # imbalance ratio
        ])
    return np.array(rows)


# ── Model lifecycle ───────────────────────────────────────────────────────────

def _get_model():
    global _iso_model
    if _iso_model is not None:
        return _iso_model

    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    logger.info("Training AML Isolation Forest on synthetic normal profiles…")
    X = _generate_normal_profiles(4000)

    _iso_model = Pipeline([
        ("scaler", StandardScaler()),
        ("iso",    IsolationForest(
            n_estimators=200,
            contamination=0.05,   # expect ~5% anomalies in real data
            random_state=42,
        )),
    ])
    _iso_model.fit(X)
    logger.info("AML model ready.")
    return _iso_model


# ── Rule engine ───────────────────────────────────────────────────────────────

_STRUCTURING_50K = AMLFlag(
    code="STRUCTURING_50K",
    severity="HIGH",
    description="Multiple transactions clustered just below ₹50,000 — classic structuring to avoid bank reporting.",
    pmla_reference="PMLA §12 / RBI Master Direction on KYC §38(c)",
)

_STRUCTURING_10L = AMLFlag(
    code="STRUCTURING_10L",
    severity="CRITICAL",
    description="Transactions clustered just below ₹10,00,000 — structured to avoid CTR (Cash Transaction Report).",
    pmla_reference="PMLA §12 — CTR mandatory for cash txns ≥ ₹10L",
)

_DORMANCY_REVIVAL = AMLFlag(
    code="DORMANCY_REVIVAL",
    severity="MEDIUM",
    description="Account was dormant for an extended period and then became highly active — common money-mule indicator.",
    pmla_reference="RBI Master Direction on KYC §41 — enhanced due diligence for dormant accounts",
)

_HIGH_CASH_RATIO = AMLFlag(
    code="HIGH_CASH_RATIO",
    severity="MEDIUM",
    description="Cash deposits exceed 40% of total credits — unusual for a salaried/business account.",
    pmla_reference="RBI KYC Directions §35 — cash-intensive accounts require enhanced monitoring",
)

_HIGH_VELOCITY = AMLFlag(
    code="HIGH_VELOCITY",
    severity="MEDIUM",
    description="Unusually high transaction frequency (>80 transactions in 90 days) without proportionate business explanation.",
    pmla_reference="RBI FIU India — velocity-based STR trigger",
)

_LARGE_SINGLE = AMLFlag(
    code="LARGE_SINGLE_TXN",
    severity="HIGH",
    description="Single transaction exceeds ₹5,00,000 — requires source-of-funds documentation.",
    pmla_reference="PMLA §12 — STR (Suspicious Transaction Report) obligation",
)

_ROUND_TRIPPING = AMLFlag(
    code="ROUND_TRIPPING",
    severity="HIGH",
    description="High proportion of round-number transactions (>60%) — potential layering indicator.",
    pmla_reference="FATF Recommendation 20 — unusual transaction patterns",
)

_INTERNATIONAL = AMLFlag(
    code="INTERNATIONAL_EXPOSURE",
    severity="MEDIUM",
    description="Multiple international transactions detected — requires FEMA compliance check.",
    pmla_reference="FEMA 1999 / RBI KYC Directions §36",
)


def _run_rules(p: TransactionProfile) -> List[AMLFlag]:
    flags = []
    safe_txns = max(p.total_transactions_90d, 1)
    safe_credits = max(p.total_credits_90d, 1)

    if p.txns_just_below_50k >= 3:
        flags.append(_STRUCTURING_50K)

    if p.txns_just_below_10l >= 2:
        flags.append(_STRUCTURING_10L)

    if p.dormancy_months >= 6 and p.total_transactions_90d >= 10:
        flags.append(_DORMANCY_REVIVAL)

    if (p.cash_deposit_total / safe_credits) > 0.40:
        flags.append(_HIGH_CASH_RATIO)

    if p.total_transactions_90d > 80:
        flags.append(_HIGH_VELOCITY)

    if p.largest_single_txn >= 500_000:
        flags.append(_LARGE_SINGLE)

    if (p.round_number_txns / safe_txns) > 0.60:
        flags.append(_ROUND_TRIPPING)

    if p.international_txns >= 5:
        flags.append(_INTERNATIONAL)

    return flags


# ── Score mapping ─────────────────────────────────────────────────────────────

def _risk_level(anomaly_score: float, flag_count: int) -> str:
    if anomaly_score >= 75 or flag_count >= 3:
        return "CRITICAL"
    if anomaly_score >= 55 or flag_count >= 2:
        return "HIGH"
    if anomaly_score >= 35 or flag_count >= 1:
        return "MEDIUM"
    return "LOW"


# ── Public API ────────────────────────────────────────────────────────────────

def run_aml_check(p: TransactionProfile) -> AMLResult:
    model = _get_model()
    X = _extract_features(p).reshape(1, -1)

    # Isolation Forest: -1 = anomaly, +1 = normal
    # decision_function gives raw score; more negative = more anomalous
    raw_score = float(model.decision_function(X)[0])

    # Map to 0-100 (higher = more suspicious)
    # Typical clean range: 0.05–0.25, anomalies: negative
    anomaly_score = round(max(0.0, min(100.0, (0.25 - raw_score) / 0.40 * 100)), 1)

    flags = _run_rules(p)
    risk  = _risk_level(anomaly_score, len(flags))

    sar_required = risk in ("HIGH", "CRITICAL") or any(f.severity == "CRITICAL" for f in flags)
    ctr_required = p.cash_deposit_total >= 1_000_000 or p.txns_just_below_10l >= 1

    summary_parts = [f"Anomaly score {anomaly_score}/100 ({risk} risk)."]
    if flags:
        summary_parts.append(f"{len(flags)} rule flag(s): {', '.join(f.code for f in flags)}.")
    if sar_required:
        summary_parts.append("STR filing recommended.")
    if ctr_required:
        summary_parts.append("CTR filing required under PMLA §12.")

    return AMLResult(
        applicant_id=p.applicant_id,
        anomaly_score=anomaly_score,
        risk_level=risk,
        flags=flags,
        ml_isolation_score=round(raw_score, 4),
        rule_flags_triggered=len(flags),
        pmla_sar_required=sar_required,
        pmla_ctr_required=ctr_required,
        audit_summary=" ".join(summary_parts),
    )

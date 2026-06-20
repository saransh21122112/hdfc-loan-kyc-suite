import uuid
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from typing import List, Optional

from kyc_engine.core.security import get_current_user
from kyc_engine.services.aml_engine import TransactionProfile, AMLFlag, run_aml_check

router = APIRouter()


class AMLRequest(BaseModel):
    applicant_id: str
    total_transactions_90d: int = Field(..., ge=0)
    total_credits_90d: float = Field(..., ge=0)
    total_debits_90d: float = Field(..., ge=0)
    cash_deposits_count: int = Field(0, ge=0)
    cash_deposit_total: float = Field(0, ge=0)
    txns_just_below_50k: int = Field(0, ge=0, description="Transactions between ₹45,000–₹49,999")
    txns_just_below_10l: int = Field(0, ge=0, description="Transactions between ₹9,00,000–₹9,99,999")
    largest_single_txn: float = Field(0, ge=0)
    round_number_txns: int = Field(0, ge=0)
    international_txns: int = Field(0, ge=0)
    account_age_months: int = Field(..., ge=0)
    dormancy_months: int = Field(0, ge=0)
    peak_balance: float = Field(0, ge=0)
    kyc_request_id: Optional[str] = None


class AMLFlagOut(BaseModel):
    code: str
    severity: str
    description: str
    pmla_reference: str


class AMLResponse(BaseModel):
    check_id: str
    applicant_id: str
    anomaly_score: float
    risk_level: str
    flags: List[AMLFlagOut]
    rule_flags_triggered: int
    pmla_sar_required: bool
    pmla_ctr_required: bool
    audit_summary: str
    model_version: str


@router.post(
    "/check",
    response_model=AMLResponse,
    status_code=status.HTTP_200_OK,
    summary="AML compliance check — Isolation Forest anomaly detection + PMLA rule engine",
)
async def aml_check(
    req: AMLRequest,
    current_user: str = Depends(get_current_user),
):
    profile = TransactionProfile(
        applicant_id=req.applicant_id,
        total_transactions_90d=req.total_transactions_90d,
        total_credits_90d=req.total_credits_90d,
        total_debits_90d=req.total_debits_90d,
        cash_deposits_count=req.cash_deposits_count,
        cash_deposit_total=req.cash_deposit_total,
        txns_just_below_50k=req.txns_just_below_50k,
        txns_just_below_10l=req.txns_just_below_10l,
        largest_single_txn=req.largest_single_txn,
        round_number_txns=req.round_number_txns,
        international_txns=req.international_txns,
        account_age_months=req.account_age_months,
        dormancy_months=req.dormancy_months,
        peak_balance=req.peak_balance,
    )

    result = run_aml_check(profile)

    return AMLResponse(
        check_id=str(uuid.uuid4()),
        applicant_id=result.applicant_id,
        anomaly_score=result.anomaly_score,
        risk_level=result.risk_level,
        flags=[AMLFlagOut(**vars(f)) for f in result.flags],
        rule_flags_triggered=result.rule_flags_triggered,
        pmla_sar_required=result.pmla_sar_required,
        pmla_ctr_required=result.pmla_ctr_required,
        audit_summary=result.audit_summary,
        model_version=result.model_version,
    )

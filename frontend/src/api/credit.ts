const BASE = '/api/v1'

export interface CreditRequest {
  applicant_id: string
  monthly_income: number
  monthly_expenses: number
  existing_emis: number
  loan_amount_requested: number
  loan_tenure_months: number
  employment_type: string
  years_employed: number
  kyc_request_id?: string
}

export interface FactorItem {
  factor: string
  impact: number
}

export interface CreditResponse {
  assessment_id: string
  applicant_id: string
  credit_score: number
  decision: 'APPROVE' | 'REVIEW' | 'REJECT'
  max_loan_eligible: number
  proposed_emi: number
  interest_rate_band: string
  top_positive_factors: FactorItem[]
  top_negative_factors: FactorItem[]
  features_used: Record<string, number>
  shap_values: Record<string, number>
  model_version: string
  rbi_audit_note: string
}

export async function assessCredit(token: string, req: CreditRequest): Promise<CreditResponse> {
  const res = await fetch(`${BASE}/credit/assess`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail ?? 'Credit assessment failed')
  }
  return res.json()
}

const BASE = '/api/v1'

export interface AMLRequest {
  applicant_id: string
  total_transactions_90d: number
  total_credits_90d: number
  total_debits_90d: number
  cash_deposits_count: number
  cash_deposit_total: number
  txns_just_below_50k: number
  txns_just_below_10l: number
  largest_single_txn: number
  round_number_txns: number
  international_txns: number
  account_age_months: number
  dormancy_months: number
  peak_balance: number
  kyc_request_id?: string
}

export interface AMLFlag {
  code: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  description: string
  pmla_reference: string
}

export interface AMLResponse {
  check_id: string
  applicant_id: string
  anomaly_score: number
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  flags: AMLFlag[]
  rule_flags_triggered: number
  pmla_sar_required: boolean
  pmla_ctr_required: boolean
  audit_summary: string
  model_version: string
}

export async function runAMLCheck(token: string, req: AMLRequest): Promise<AMLResponse> {
  const res = await fetch(`${BASE}/aml/check`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail ?? 'AML check failed')
  }
  return res.json()
}

import { useState } from 'react'
import { runAMLCheck, AMLResponse, AMLFlag } from '../api/aml'

interface Props {
  token: string
  applicantId: string
  kycRequestId?: string
}

const RISK_COLOR = {
  LOW:      { bg: '#d1fae5', text: '#065f46', border: '#6ee7b7', bar: '#10b981' },
  MEDIUM:   { bg: '#fef3c7', text: '#92400e', border: '#fcd34d', bar: '#f59e0b' },
  HIGH:     { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5', bar: '#ef4444' },
  CRITICAL: { bg: '#fce7f3', text: '#9d174d', border: '#f9a8d4', bar: '#db2777' },
}

const SEV_COLOR: Record<string, string> = {
  LOW: '#10b981', MEDIUM: '#f59e0b', HIGH: '#ef4444', CRITICAL: '#db2777',
}

function RiskGauge({ score, level }: { score: number; level: string }) {
  const c = RISK_COLOR[level as keyof typeof RISK_COLOR] ?? RISK_COLOR.LOW
  return (
    <div style={{ textAlign: 'center', padding: '8px 0' }}>
      <div style={{ fontSize: 52, fontWeight: 800, color: c.bar, lineHeight: 1 }}>
        {score.toFixed(0)}
      </div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Anomaly Score (0 = clean · 100 = highly suspicious)</div>
      <div style={{ margin: '10px auto 0', height: 10, width: '100%', maxWidth: 260, background: '#e5e7eb', borderRadius: 6, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${score}%`, background: `linear-gradient(90deg, #10b981, #f59e0b, #ef4444, #db2777)`, borderRadius: 6, transition: 'width 0.8s ease' }} />
      </div>
    </div>
  )
}

function FlagCard({ flag }: { flag: AMLFlag }) {
  const color = SEV_COLOR[flag.severity] ?? '#6b7280'
  return (
    <div style={{ border: `1px solid ${color}22`, borderLeft: `4px solid ${color}`, borderRadius: 8, padding: '12px 16px', marginBottom: 10, background: `${color}08` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
        <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: color, color: '#fff' }}>
          {flag.severity}
        </span>
        <span style={{ fontSize: 13, fontWeight: 700, color: '#111827', fontFamily: 'monospace' }}>{flag.code}</span>
      </div>
      <p style={{ margin: '0 0 6px', fontSize: 13, color: '#374151', lineHeight: 1.5 }}>{flag.description}</p>
      <p style={{ margin: 0, fontSize: 11, color: '#6b7280' }}>📋 {flag.pmla_reference}</p>
    </div>
  )
}

const FIELD = (label: string, key: string, value: string, onChange: (k: string, v: string) => void, hint = '') => (
  <div style={{ marginBottom: 14 }}>
    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 3 }}>
      {label}{hint && <span style={{ color: '#9ca3af', fontWeight: 400 }}> · {hint}</span>}
    </label>
    <input
      type="number"
      value={value}
      onChange={e => onChange(key, e.target.value)}
      style={{ width: '100%', padding: '7px 11px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 13, boxSizing: 'border-box' }}
    />
  </div>
)

const DEFAULTS = {
  total_transactions_90d: '28',
  total_credits_90d: '255000',
  total_debits_90d: '190000',
  cash_deposits_count: '2',
  cash_deposit_total: '15000',
  txns_just_below_50k: '0',
  txns_just_below_10l: '0',
  largest_single_txn: '45000',
  round_number_txns: '6',
  international_txns: '0',
  account_age_months: '36',
  dormancy_months: '0',
  peak_balance: '120000',
}

export function AMLMonitor({ token, applicantId, kycRequestId }: Props) {
  const [form, setForm] = useState(DEFAULTS)
  const [result, setResult] = useState<AMLResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await runAMLCheck(token, {
        applicant_id: applicantId,
        total_transactions_90d: Number(form.total_transactions_90d),
        total_credits_90d: Number(form.total_credits_90d),
        total_debits_90d: Number(form.total_debits_90d),
        cash_deposits_count: Number(form.cash_deposits_count),
        cash_deposit_total: Number(form.cash_deposit_total),
        txns_just_below_50k: Number(form.txns_just_below_50k),
        txns_just_below_10l: Number(form.txns_just_below_10l),
        largest_single_txn: Number(form.largest_single_txn),
        round_number_txns: Number(form.round_number_txns),
        international_txns: Number(form.international_txns),
        account_age_months: Number(form.account_age_months),
        dormancy_months: Number(form.dormancy_months),
        peak_balance: Number(form.peak_balance),
        kyc_request_id: kycRequestId,
      })
      setResult(res)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const rc = result ? RISK_COLOR[result.risk_level as keyof typeof RISK_COLOR] : null

  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: '0 16px 40px' }}>
      {/* Suspicious scenario presets */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        <span style={{ fontSize: 12, color: '#6b7280', alignSelf: 'center' }}>Quick scenarios:</span>
        <button onClick={() => setForm(DEFAULTS)} style={presetBtn('#10b981')}>✅ Clean Profile</button>
        <button onClick={() => setForm({ ...DEFAULTS, txns_just_below_50k: '5', cash_deposits_count: '8', cash_deposit_total: '240000', round_number_txns: '18' })} style={presetBtn('#ef4444')}>🚨 Structuring</button>
        <button onClick={() => setForm({ ...DEFAULTS, dormancy_months: '18', total_transactions_90d: '55', largest_single_txn: '680000' })} style={presetBtn('#f59e0b')}>⚠️ Dormancy Revival</button>
        <button onClick={() => setForm({ ...DEFAULTS, international_txns: '12', txns_just_below_10l: '3', largest_single_txn: '950000' })} style={presetBtn('#db2777')}>🔴 High Risk</button>
      </div>

      <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 24, marginBottom: 20 }}>
        <h2 style={{ margin: '0 0 4px', fontSize: 19, fontWeight: 700, color: '#111827' }}>AML Compliance Monitor</h2>
        <p style={{ margin: '0 0 18px', fontSize: 12, color: '#6b7280' }}>
          Isolation Forest anomaly detection + PMLA rule engine · Applicant {applicantId}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '0 16px' }}>
          {FIELD('Total Transactions (90d)', 'total_transactions_90d', form.total_transactions_90d, set)}
          {FIELD('Total Credits ₹', 'total_credits_90d', form.total_credits_90d, set)}
          {FIELD('Total Debits ₹', 'total_debits_90d', form.total_debits_90d, set)}
          {FIELD('Cash Deposits Count', 'cash_deposits_count', form.cash_deposits_count, set)}
          {FIELD('Cash Deposit Total ₹', 'cash_deposit_total', form.cash_deposit_total, set)}
          {FIELD('Largest Single Txn ₹', 'largest_single_txn', form.largest_single_txn, set)}
          {FIELD('Txns ₹45k–₹49,999', 'txns_just_below_50k', form.txns_just_below_50k, set, 'structuring')}
          {FIELD('Txns ₹9L–₹9,99,999', 'txns_just_below_10l', form.txns_just_below_10l, set, 'CTR threshold')}
          {FIELD('Round Number Txns', 'round_number_txns', form.round_number_txns, set)}
          {FIELD('International Txns', 'international_txns', form.international_txns, set)}
          {FIELD('Account Age (months)', 'account_age_months', form.account_age_months, set)}
          {FIELD('Dormancy (months)', 'dormancy_months', form.dormancy_months, set)}
        </div>

        {error && <div style={{ background: '#fee2e2', color: '#991b1b', padding: '10px 14px', borderRadius: 6, marginBottom: 14, fontSize: 13 }}>{error}</div>}

        <button
          onClick={submit}
          disabled={loading}
          style={{ width: '100%', padding: '12px 0', background: loading ? '#9ca3af' : '#1e3a5f', color: '#fff', border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer', marginTop: 4 }}
        >
          {loading ? '⏳ Running AML Check…' : '🔍 Run AML Compliance Check'}
        </button>
      </div>

      {result && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 24 }}>
          {/* Score + Risk level */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
            <RiskGauge score={result.anomaly_score} level={result.risk_level} />
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 10 }}>
              <div style={{ padding: '10px 16px', borderRadius: 8, fontWeight: 800, fontSize: 22, textAlign: 'center', border: `2px solid ${rc!.border}`, background: rc!.bg, color: rc!.text }}>
                {result.risk_level === 'LOW' ? '✅' : result.risk_level === 'MEDIUM' ? '⚠️' : result.risk_level === 'HIGH' ? '🚨' : '🔴'} {result.risk_level} RISK
              </div>
              <div style={{ fontSize: 12, lineHeight: 1.7 }}>
                <div style={{ color: result.pmla_sar_required ? '#dc2626' : '#059669', fontWeight: 600 }}>
                  {result.pmla_sar_required ? '⚠️ STR Filing Required' : '✓ No STR Required'}
                </div>
                <div style={{ color: result.pmla_ctr_required ? '#dc2626' : '#059669', fontWeight: 600 }}>
                  {result.pmla_ctr_required ? '⚠️ CTR Filing Required' : '✓ No CTR Required'}
                </div>
                <div style={{ color: '#6b7280', marginTop: 4 }}>
                  {result.rule_flags_triggered} rule flag{result.rule_flags_triggered !== 1 ? 's' : ''} triggered
                </div>
              </div>
            </div>
          </div>

          {/* Flags */}
          {result.flags.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#111827' }}>
                🚩 PMLA Flags ({result.flags.length})
              </h3>
              {result.flags.map(f => <FlagCard key={f.code} flag={f} />)}
            </div>
          )}

          {result.flags.length === 0 && (
            <div style={{ background: '#d1fae5', border: '1px solid #6ee7b7', borderRadius: 8, padding: '12px 16px', marginBottom: 20, color: '#065f46', fontSize: 13, fontWeight: 600 }}>
              ✅ No PMLA flags triggered. Transaction patterns are within normal range.
            </div>
          )}

          {/* Audit trail */}
          <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 16px', fontSize: 11, color: '#64748b', lineHeight: 1.6 }}>
            <strong>PMLA Audit Trail</strong> · Model: {result.model_version}<br />
            {result.audit_summary}
          </div>
        </div>
      )}
    </div>
  )
}

const presetBtn = (color: string) => ({
  padding: '5px 12px', border: `1px solid ${color}`, borderRadius: 6,
  background: `${color}15`, color, fontSize: 12, fontWeight: 600, cursor: 'pointer',
})

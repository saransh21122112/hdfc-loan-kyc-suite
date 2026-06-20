import { useState } from 'react'
import { assessCredit, CreditResponse } from '../api/credit'

interface Props {
  token: string
  applicantId: string
  kycRequestId?: string
}

const DECISION_COLOR = {
  APPROVE: { bg: '#d1fae5', text: '#065f46', border: '#6ee7b7' },
  REVIEW:  { bg: '#fef3c7', text: '#92400e', border: '#fcd34d' },
  REJECT:  { bg: '#fee2e2', text: '#991b1b', border: '#fca5a5' },
}

function ScoreGauge({ score }: { score: number }) {
  const pct = ((score - 300) / 600) * 100
  const color = score >= 700 ? '#10b981' : score >= 600 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ textAlign: 'center', padding: '8px 0' }}>
      <div style={{ fontSize: 52, fontWeight: 800, color, lineHeight: 1 }}>{score}</div>
      <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>Credit Score (CIBIL scale 300–900)</div>
      <div style={{
        margin: '10px auto 0', height: 10, width: '100%', maxWidth: 260,
        background: '#e5e7eb', borderRadius: 6, overflow: 'hidden',
      }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: `linear-gradient(90deg, #ef4444, #f59e0b, #10b981)`,
          borderRadius: 6, transition: 'width 0.8s ease',
        }} />
      </div>
    </div>
  )
}

function FactorBar({ label, impact, max }: { label: string; impact: number; max: number }) {
  const pct = Math.min(Math.abs(impact) / max * 100, 100)
  const positive = impact > 0
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 3 }}>
        <span style={{ color: '#374151' }}>{label}</span>
        <span style={{ color: positive ? '#059669' : '#dc2626', fontWeight: 600 }}>
          {positive ? '▲' : '▼'} {Math.abs(impact).toFixed(3)}
        </span>
      </div>
      <div style={{ height: 6, background: '#f3f4f6', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%', width: `${pct}%`,
          background: positive ? '#10b981' : '#ef4444',
          borderRadius: 3,
        }} />
      </div>
    </div>
  )
}

export function CreditAssessment({ token, applicantId, kycRequestId }: Props) {
  const [form, setForm] = useState({
    monthly_income: '',
    monthly_expenses: '',
    existing_emis: '0',
    loan_amount_requested: '',
    loan_tenure_months: '36',
    employment_type: 'salaried',
    years_employed: '',
  })
  const [result, setResult] = useState<CreditResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  const submit = async () => {
    setLoading(true); setError(''); setResult(null)
    try {
      const res = await assessCredit(token, {
        applicant_id: applicantId,
        monthly_income: Number(form.monthly_income),
        monthly_expenses: Number(form.monthly_expenses),
        existing_emis: Number(form.existing_emis),
        loan_amount_requested: Number(form.loan_amount_requested),
        loan_tenure_months: Number(form.loan_tenure_months),
        employment_type: form.employment_type,
        years_employed: Number(form.years_employed),
        kyc_request_id: kycRequestId,
      })
      setResult(res)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const inp = (label: string, key: string, type = 'number', placeholder = '') => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
        {label}
      </label>
      <input
        type={type}
        value={(form as any)[key]}
        onChange={e => set(key, e.target.value)}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '8px 12px', border: '1px solid #d1d5db',
          borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
        }}
      />
    </div>
  )

  const dc = result ? DECISION_COLOR[result.decision] : null
  const maxImpact = result
    ? Math.max(...[...result.top_positive_factors, ...result.top_negative_factors].map(f => Math.abs(f.impact)), 0.001)
    : 0.001

  return (
    <div style={{ maxWidth: 680, margin: '0 auto', padding: '0 16px 40px' }}>
      <div style={{
        background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb',
        padding: 28, marginBottom: 24,
      }}>
        <h2 style={{ margin: '0 0 6px', fontSize: 20, fontWeight: 700, color: '#111827' }}>
          AI Credit Underwriting
        </h2>
        <p style={{ margin: '0 0 20px', fontSize: 13, color: '#6b7280' }}>
          XGBoost score + SHAP explainability · Applicant {applicantId}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 20px' }}>
          {inp('Monthly Income (₹)', 'monthly_income', 'number', '85000')}
          {inp('Monthly Expenses (₹)', 'monthly_expenses', 'number', '40000')}
          {inp('Existing EMIs (₹)', 'existing_emis', 'number', '0')}
          {inp('Loan Amount Requested (₹)', 'loan_amount_requested', 'number', '500000')}
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
              Loan Tenure (months)
            </label>
            <select
              value={form.loan_tenure_months}
              onChange={e => set('loan_tenure_months', e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
            >
              {[12, 24, 36, 48, 60, 84, 120].map(m => (
                <option key={m} value={m}>{m} months ({(m/12).toFixed(0)} yr{m > 12 ? 's' : ''})</option>
              ))}
            </select>
          </div>
          <div style={{ marginBottom: 14 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 4 }}>
              Employment Type
            </label>
            <select
              value={form.employment_type}
              onChange={e => set('employment_type', e.target.value)}
              style={{ width: '100%', padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 14 }}
            >
              <option value="salaried">Salaried</option>
              <option value="self_employed">Self Employed</option>
              <option value="business">Business Owner</option>
            </select>
          </div>
          {inp('Years at Current Job / Business', 'years_employed', 'number', '3')}
        </div>

        {error && (
          <div style={{ background: '#fee2e2', color: '#991b1b', padding: '10px 14px', borderRadius: 6, marginBottom: 14, fontSize: 13 }}>
            {error}
          </div>
        )}

        <button
          onClick={submit}
          disabled={loading}
          style={{
            width: '100%', padding: '12px 0', background: loading ? '#9ca3af' : '#1e3a5f',
            color: '#fff', border: 'none', borderRadius: 8, fontSize: 15, fontWeight: 700,
            cursor: loading ? 'not-allowed' : 'pointer', marginTop: 4,
          }}
        >
          {loading ? '⏳ Assessing…' : '🧠 Run Credit Assessment'}
        </button>
      </div>

      {result && (
        <div style={{ background: '#fff', borderRadius: 12, border: '1px solid #e5e7eb', padding: 28 }}>
          {/* Score + Decision */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
            <ScoreGauge score={result.credit_score} />
            <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: 12 }}>
              <div style={{
                padding: '10px 16px', borderRadius: 8, fontWeight: 800, fontSize: 22,
                textAlign: 'center', border: `2px solid ${dc!.border}`,
                background: dc!.bg, color: dc!.text,
              }}>
                {result.decision === 'APPROVE' ? '✅' : result.decision === 'REVIEW' ? '🔍' : '❌'} {result.decision}
              </div>
              <div style={{ fontSize: 13, color: '#374151', lineHeight: 1.6 }}>
                <div><strong>Proposed EMI:</strong> ₹{result.proposed_emi.toLocaleString('en-IN')}/mo</div>
                <div><strong>Max Eligible:</strong> ₹{result.max_loan_eligible.toLocaleString('en-IN')}</div>
                <div><strong>Rate Band:</strong> {result.interest_rate_band}</div>
              </div>
            </div>
          </div>

          {/* SHAP Factors */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
            <div>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#065f46' }}>
                ▲ Positive Factors
              </h3>
              {result.top_positive_factors.map(f => (
                <FactorBar key={f.factor} label={f.factor} impact={f.impact} max={maxImpact} />
              ))}
              {result.top_positive_factors.length === 0 && (
                <p style={{ fontSize: 12, color: '#9ca3af' }}>None identified</p>
              )}
            </div>
            <div>
              <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700, color: '#991b1b' }}>
                ▼ Risk Factors
              </h3>
              {result.top_negative_factors.map(f => (
                <FactorBar key={f.factor} label={f.factor} impact={f.impact} max={maxImpact} />
              ))}
              {result.top_negative_factors.length === 0 && (
                <p style={{ fontSize: 12, color: '#9ca3af' }}>None identified</p>
              )}
            </div>
          </div>

          {/* RBI Audit Trail */}
          <div style={{
            background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8,
            padding: '12px 16px', fontSize: 11, color: '#64748b', lineHeight: 1.5,
          }}>
            <strong>RBI Audit Trail</strong> · Model: {result.model_version}<br />
            {result.rbi_audit_note}
          </div>
        </div>
      )}
    </div>
  )
}

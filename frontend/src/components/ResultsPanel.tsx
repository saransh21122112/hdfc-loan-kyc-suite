import { KYCResult, ValidationCheck, DocumentResult, ExtractedField } from '../api/kyc'

interface Props { result: KYCResult }

export default function ResultsPanel({ result }: Props) {
  const hasFlags = result.flags.length > 0
  const failCount = result.validation_checks.filter(c => c.status === 'fail').length
  const warnCount = result.validation_checks.filter(c => c.status === 'warning').length
  const passCount = result.validation_checks.filter(c => c.status === 'pass').length

  return (
    <div className="results">
      {/* Summary bar */}
      <div className={`summary-bar ${hasFlags ? 'summary-bar--warn' : 'summary-bar--ok'}`}>
        <div className="summary-left">
          <span className="summary-icon">{hasFlags ? '⚠️' : '✅'}</span>
          <div>
            <div className="summary-title">
              {hasFlags ? 'Review Required' : 'All Checks Passed'}
            </div>
            <div className="summary-meta">
              Applicant {result.applicant_id} · {result.documents_processed} document(s) ·{' '}
              {result.processing_time_ms} ms
            </div>
          </div>
        </div>
        <div className="summary-counts">
          <span className="badge badge--pass">{passCount} Pass</span>
          {warnCount > 0 && <span className="badge badge--warn">{warnCount} Warning</span>}
          {failCount > 0 && <span className="badge badge--fail">{failCount} Fail</span>}
        </div>
      </div>

      {/* Flags */}
      {result.flags.length > 0 && (
        <div className="section">
          <h3 className="section-title">🚩 Flags</h3>
          <div className="flags">
            {result.flags.map((f, i) => (
              <div key={i} className={`flag ${f.startsWith('[FAIL]') ? 'flag--fail' : 'flag--warn'}`}>
                {f}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Validation checks */}
      <div className="section">
        <h3 className="section-title">✔ Validation Checks</h3>
        <div className="checks">
          {result.validation_checks.map((c, i) => (
            <CheckRow key={i} check={c} />
          ))}
        </div>
      </div>

      {/* Extracted fields per document */}
      {result.document_results.map(doc => (
        <DocumentCard key={doc.document_id} doc={doc} />
      ))}
    </div>
  )
}

function CheckRow({ check }: { check: ValidationCheck }) {
  const icons = { pass: '✅', fail: '❌', warning: '⚠️', skipped: '⏭' }
  const classes = { pass: 'check--pass', fail: 'check--fail', warning: 'check--warn', skipped: 'check--skip' }

  return (
    <div className={`check-row ${classes[check.status]}`}>
      <span className="check-icon">{icons[check.status]}</span>
      <div className="check-body">
        <div className="check-name">{check.check_name.replace(/_/g, ' ')}</div>
        <div className="check-msg">{check.message}</div>
      </div>
    </div>
  )
}

function DocumentCard({ doc }: { doc: DocumentResult }) {
  const fields = Object.entries(doc.extracted_fields).filter(([, v]) => v?.value)

  return (
    <div className="section">
      <h3 className="section-title">
        📄 {doc.document_type} — {doc.file_name}
        <span className="ocr-conf">OCR confidence: {(doc.ocr_confidence * 100).toFixed(0)}%</span>
      </h3>
      {fields.length === 0 ? (
        <p className="no-fields">No fields extracted. Check OCR confidence above.</p>
      ) : (
        <div className="fields-grid">
          {fields.map(([key, field]) => (
            <FieldRow key={key} label={key} field={field as ExtractedField} />
          ))}
        </div>
      )}
    </div>
  )
}

function FieldRow({ label, field }: { label: string; field: ExtractedField }) {
  const conf = field.confidence
  const confClass = conf >= 0.9 ? 'conf--high' : conf >= 0.7 ? 'conf--med' : 'conf--low'

  return (
    <div className="field-row">
      <div className="field-label">{label.replace(/_/g, ' ')}</div>
      <div className="field-value">{field.value ?? '—'}</div>
      <div className={`field-conf ${confClass}`}>{(conf * 100).toFixed(0)}%</div>
      <div className="field-source">{field.source}</div>
    </div>
  )
}

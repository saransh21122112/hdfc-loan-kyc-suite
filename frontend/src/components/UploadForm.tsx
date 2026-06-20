import { useState, useRef, DragEvent } from 'react'

interface Props {
  onExtract: (applicantId: string, files: File[]) => void
  loading: boolean
}

export default function UploadForm({ onExtract, loading }: Props) {
  const [applicantId, setApplicantId] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function addFiles(incoming: FileList | null) {
    if (!incoming) return
    const valid = Array.from(incoming).filter(f =>
      ['image/png', 'image/jpeg', 'image/tiff', 'application/pdf'].includes(f.type)
    )
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...valid.filter(f => !names.has(f.name))]
    })
  }

  function removeFile(name: string) {
    setFiles(prev => prev.filter(f => f.name !== name))
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragging(false)
    addFiles(e.dataTransfer.files)
  }

  const canSubmit = applicantId.trim() && files.length > 0 && !loading

  return (
    <div className="card upload-card">
      <h2 className="card-title">KYC Document Extraction</h2>
      <p className="card-sub">
        Upload PAN card, Aadhaar card, or bank statement. The AI will extract fields
        and cross-validate data across documents.
      </p>

      <div className="field">
        <label>Applicant ID</label>
        <input
          placeholder="e.g. APP-001234"
          value={applicantId}
          onChange={e => setApplicantId(e.target.value)}
        />
      </div>

      <div className="field">
        <label>Documents</label>
        <div
          className={`drop-zone ${dragging ? 'dragging' : ''}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".png,.jpg,.jpeg,.tiff,.pdf"
            style={{ display: 'none' }}
            onChange={e => addFiles(e.target.files)}
          />
          <div className="drop-icon">📄</div>
          <div className="drop-text">
            <strong>Click to upload</strong> or drag and drop
          </div>
          <div className="drop-hint">PNG, JPEG, TIFF, PDF · Max 10 MB each</div>
        </div>
      </div>

      {files.length > 0 && (
        <div className="file-list">
          {files.map(f => (
            <div key={f.name} className="file-item">
              <span className="file-icon">📎</span>
              <span className="file-name">{f.name}</span>
              <span className="file-size">{(f.size / 1024).toFixed(0)} KB</span>
              <button className="file-remove" onClick={() => removeFile(f.name)}>✕</button>
            </div>
          ))}
        </div>
      )}

      <button
        className="btn-primary"
        disabled={!canSubmit}
        onClick={() => onExtract(applicantId.trim(), files)}
      >
        {loading ? (
          <><span className="spinner" /> Extracting…</>
        ) : (
          '⚡ Extract & Validate'
        )}
      </button>
    </div>
  )
}

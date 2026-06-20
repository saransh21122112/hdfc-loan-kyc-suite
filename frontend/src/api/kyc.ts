const BASE = '/api/v1'

export async function getToken(username: string, password: string): Promise<string> {
  const form = new FormData()
  form.append('username', username)
  form.append('password', password)

  const res = await fetch(`${BASE}/auth/token`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('Invalid credentials')
  const data = await res.json()
  return data.access_token
}

export async function extractKYC(
  token: string,
  applicantId: string,
  files: File[]
): Promise<KYCResult> {
  const form = new FormData()
  form.append('applicant_id', applicantId)
  files.forEach(f => form.append('files', f))

  const res = await fetch(`${BASE}/kyc/extract`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Unknown error' }))
    throw new Error(err.detail ?? 'Extraction failed')
  }
  return res.json()
}

export interface ExtractedField {
  value: string | null
  confidence: number
  source: string
}

export interface DocumentResult {
  document_id: string
  file_name: string
  document_type: string
  ocr_confidence: number
  extracted_fields: Record<string, ExtractedField | null>
}

export interface ValidationCheck {
  check_name: string
  status: 'pass' | 'fail' | 'warning' | 'skipped'
  message: string
  documents_compared: string[]
}

export interface KYCResult {
  request_id: string
  applicant_id: string
  status: string
  documents_processed: number
  document_results: DocumentResult[]
  validation_checks: ValidationCheck[]
  flags: string[]
  processing_time_ms: number
  created_at: string
}

import { useState } from 'react'
import { getToken, extractKYC, KYCResult } from './api/kyc'
import UploadForm from './components/UploadForm'
import ResultsPanel from './components/ResultsPanel'
import './App.css'

type Screen = 'login' | 'upload' | 'results'

export default function App() {
  const [screen, setScreen] = useState<Screen>('login')
  const [token, setToken] = useState('')
  const [result, setResult] = useState<KYCResult | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(username: string, password: string) {
    setLoading(true)
    setError('')
    try {
      const t = await getToken(username, password)
      setToken(t)
      setScreen('upload')
    } catch {
      setError('Invalid credentials. Try demo / demo123')
    } finally {
      setLoading(false)
    }
  }

  async function handleExtract(applicantId: string, files: File[]) {
    setLoading(true)
    setError('')
    try {
      const res = await extractKYC(token, applicantId, files)
      setResult(res)
      setScreen('results')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Extraction failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="logo">
            <span className="logo-mark">KYC</span>
            <div>
              <div className="logo-title">HDFC AI KYC Intelligence Suite</div>
              <div className="logo-sub">Smart Document Extraction &amp; Validation</div>
            </div>
          </div>
          {screen !== 'login' && (
            <button className="btn-ghost" onClick={() => { setScreen('upload'); setResult(null) }}>
              ← New Extraction
            </button>
          )}
        </div>
      </header>

      <main className="main">
        {error && <div className="error-banner">{error}</div>}

        {screen === 'login' && (
          <LoginCard onLogin={handleLogin} loading={loading} />
        )}
        {screen === 'upload' && (
          <UploadForm onExtract={handleExtract} loading={loading} />
        )}
        {screen === 'results' && result && (
          <ResultsPanel result={result} />
        )}
      </main>

      <footer className="footer">
        HDFC AI KYC Intelligence Suite · Powered by Tesseract OCR + FastAPI ·
        All data processed on-premise per RBI data residency norms
      </footer>
    </div>
  )
}

function LoginCard({ onLogin, loading }: { onLogin: (u: string, p: string) => void; loading: boolean }) {
  const [username, setUsername] = useState('demo')
  const [password, setPassword] = useState('demo123')

  return (
    <div className="card login-card">
      <h2 className="card-title">Sign In</h2>
      <p className="card-sub">Use <strong>demo / demo123</strong> to test the KYC extraction engine</p>

      <div className="field">
        <label>Username</label>
        <input
          value={username}
          onChange={e => setUsername(e.target.value)}
          autoComplete="username"
        />
      </div>
      <div className="field">
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={e => setPassword(e.target.value)}
          autoComplete="current-password"
          onKeyDown={e => e.key === 'Enter' && onLogin(username, password)}
        />
      </div>
      <button
        className="btn-primary"
        onClick={() => onLogin(username, password)}
        disabled={loading}
      >
        {loading ? 'Signing in…' : 'Sign In'}
      </button>
    </div>
  )
}

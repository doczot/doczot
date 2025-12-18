import { useState, useEffect } from 'react'
import './App.css'

interface Endpoint {
  method: string
  path: string
  docstring: string | null
  parameters: Array<{ name: string, type_hint: string | null }>
  analysis_method: string | null
  confidence_score: number | null
  is_documented: boolean
  matched_doc_chunk: string | null
}

interface ReviewSession {
  session_id: string
  repo_path: string
  progress: {
    total: number
    reviewed: number
    pending: number
  }
  report: {
    endpoints: Endpoint[]
  }
}

type JudgmentType = 'approve' | 'reject' | 'adjust' | 'skip'

function App() {
  const [session, setSession] = useState<ReviewSession | null>(null)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [confidence, setConfidence] = useState(0.5)
  const [loading, setLoading] = useState(false)

  const currentEndpoint = session?.report.endpoints[currentIndex]

  const submitJudgment = async (type: JudgmentType) => {
    if (!session || !currentEndpoint) return

    const judgment = {
      endpoint_id: `${currentEndpoint.method}_${currentEndpoint.path}`,
      judgment_type: type,
      adjusted_confidence: type === 'adjust' ? confidence : null,
      notes: '',
      timestamp: new Date().toISOString()
    }

    try {
      await fetch(`http://localhost:8001/sessions/${session.session_id}/judgments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(judgment)
      })

      // Move to next endpoint
      if (currentIndex < session.report.endpoints.length - 1) {
        setCurrentIndex(currentIndex + 1)
      }
    } catch (error) {
      console.error('Failed to submit judgment:', error)
    }
  }

  const loadSession = async (sessionId: string) => {
    setLoading(true)
    try {
      const res = await fetch(`http://localhost:8001/sessions/${sessionId}`)
      const data = await res.json()
      setSession(data)
    } catch (error) {
      console.error('Failed to load session:', error)
    } finally {
      setLoading(false)
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyPress = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') setCurrentIndex(i => Math.min(i + 1, (session?.report.endpoints.length || 0) - 1))
      if (e.key === 'ArrowLeft') setCurrentIndex(i => Math.max(i - 1, 0))
      if (e.key === 'a') submitJudgment('approve')
      if (e.key === 'r') submitJudgment('reject')
      if (e.key === 's') submitJudgment('skip')
    }
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [session, currentIndex])

  if (!session) {
    return (
      <div className="app">
        <h1>DocZot Expert Reviewer</h1>
        <div className="load-session">
          <input
            type="text"
            placeholder="Session ID"
            id="session-id"
            onKeyPress={(e) => {
              if (e.key === 'Enter') {
                const input = e.target as HTMLInputElement
                loadSession(input.value)
              }
            }}
          />
          <button onClick={() => {
            const input = document.getElementById('session-id') as HTMLInputElement
            loadSession(input.value)
          }}>
            Load Session
          </button>
        </div>
      </div>
    )
  }

  if (loading) return <div>Loading...</div>

  return (
    <div className="app">
      <header>
        <h1>DocZot Expert Reviewer</h1>
        <div className="progress">
          Reviewing: {currentIndex + 1} / {session.report.endpoints.length}
        </div>
      </header>

      {currentEndpoint && (
        <div className="review-interface">
          <div className="endpoint-card">
            <h2>
              <span className={`method ${currentEndpoint.method.toLowerCase()}`}>
                {currentEndpoint.method}
              </span>
              <code>{currentEndpoint.path}</code>
            </h2>

            {currentEndpoint.docstring && (
              <div className="docstring">
                <strong>Docstring:</strong>
                <p>{currentEndpoint.docstring}</p>
              </div>
            )}

            {currentEndpoint.parameters.length > 0 && (
              <div className="parameters">
                <strong>Parameters:</strong>
                <ul>
                  {currentEndpoint.parameters.map((p, i) => (
                    <li key={i}>
                      {p.name}
                      {p.type_hint && <span className="type"> : {p.type_hint}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="match-info">
              <div className="badge">
                {currentEndpoint.analysis_method || 'MISSING'}
              </div>
              {currentEndpoint.confidence_score && (
                <div className="confidence">
                  Confidence: {(currentEndpoint.confidence_score * 100).toFixed(0)}%
                </div>
              )}
            </div>
          </div>

          {/* Show matched documentation if available */}
          {currentEndpoint.is_documented && (
            <div className="documentation-viewer">
              <h3>📄 Matched Documentation</h3>
              <div className="doc-content">
                <div className="doc-meta">
                  <span className="match-type">{currentEndpoint.analysis_method?.toUpperCase()}</span>
                  <span className="score">{(currentEndpoint.confidence_score || 0) * 100}% match</span>
                </div>
                <p className="doc-note">
                  ℹ️ This is the documentation that DocZot matched to this endpoint.
                  Review whether this match is correct.
                </p>
                {currentEndpoint.matched_doc_chunk ? (
                  <div className="doc-text">
                    <pre>{currentEndpoint.matched_doc_chunk}</pre>
                  </div>
                ) : (
                  <div className="doc-placeholder">
                    <em>No matched documentation available. This may indicate an issue with the matching process.</em>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="judgment-controls">
            <button
              className="btn-approve"
              onClick={() => submitJudgment('approve')}
            >
              ✓ Approve (A)
            </button>
            <button
              className="btn-reject"
              onClick={() => submitJudgment('reject')}
            >
              ✗ Reject (R)
            </button>
            <button
              className="btn-skip"
              onClick={() => submitJudgment('skip')}
            >
              → Skip (S)
            </button>

            <div className="adjust-confidence">
              <label>
                Adjust Confidence: {(confidence * 100).toFixed(0)}%
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={confidence}
                  onChange={(e) => setConfidence(parseFloat(e.target.value))}
                />
              </label>
              <button
                className="btn-adjust"
                onClick={() => submitJudgment('adjust')}
              >
                Save Adjustment
              </button>
            </div>
          </div>

          <div className="navigation">
            <button
              onClick={() => setCurrentIndex(i => Math.max(i - 1, 0))}
              disabled={currentIndex === 0}
            >
              ← Previous
            </button>
            <button
              onClick={() => setCurrentIndex(i => Math.min(i + 1, session.report.endpoints.length - 1))}
              disabled={currentIndex === session.report.endpoints.length - 1}
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

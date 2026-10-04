import { useRef, useState } from 'react'
import RouteMap from './components/RouteMap.jsx'
import ELDLogs from './components/ELDLogs.jsx'
import TripForm from './components/TripForm.jsx'
import TripSummary from './components/TripSummary.jsx'
import TripTimeline from './components/TripTimeline.jsx'
import { planTrip } from './services/tripApi.js'

function App() {
  const [result, setResult] = useState(null)
  const [requestError, setRequestError] = useState('')
  const [loading, setLoading] = useState(false)
  const requestInFlight = useRef(false)

  async function handlePlanTrip(data) {
    if (requestInFlight.current) return
    requestInFlight.current = true
    setLoading(true)
    setRequestError('')
    setResult(null)
    try {
      setResult(await planTrip(data))
    } catch (error) {
      setRequestError(error.message)
    } finally {
      requestInFlight.current = false
      setLoading(false)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/" aria-label="Truck Trip Planner home">
          <span className="brand-mark" aria-hidden="true"><span /><span /><span /></span>
          <span className="brand-copy">
            <strong>Truck Trip Planner</strong>
            <span>HOS-compliant route planning</span>
          </span>
        </a>
        <span className="header-tag">OPERATIONS</span>
      </header>

      <main className="workspace">
        <section className="page-heading" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">TRIP WORKSPACE</p>
            <h1 id="page-title">Plan a trip</h1>
            <p className="page-description">Build a route and review the driver schedule against the available cycle.</p>
          </div>
          <div className="connection-status"><span className="status-dot" /> Live route and HOS estimate</div>
        </section>

        <div className="planner-layout">
          <aside className="form-column">
            <TripForm
              onPlanTrip={handlePlanTrip}
              loading={loading}
              requestError={requestError}
              clearRequestError={() => setRequestError('')}
            />
          </aside>

          <section className="results-column" aria-labelledby="results-title" aria-live="polite">
            <div className="results-heading">
              <div>
                <p className="eyebrow">ROUTE OVERVIEW</p>
                <h2 id="results-title">Trip results</h2>
              </div>
              {result && <span className={`result-badge ${result.status === 'completed' ? 'is-complete' : 'is-limited'}`}>
                {result.status === 'completed' ? 'Plan complete' : 'Cycle limit reached'}
              </span>}
            </div>

            {loading ? (
              <div className="empty-state plan-loading" role="status" aria-live="polite">
                <span className="button-spinner plan-loading-spinner" aria-hidden="true" />
                <h3>Planning your trip</h3>
                <p>Resolving locations and preparing the route and driver schedule.</p>
              </div>
            ) : result ? (
              <div className="results-content">
                <RouteMap result={result} />
                <TripSummary result={result} />
                <TripTimeline events={result.timeline} />
                <ELDLogs result={result} />
              </div>
            ) : (
              <div className="empty-state">
                <span className="empty-mark" aria-hidden="true">ROUTE</span>
                <h3>Your trip details will appear here</h3>
                <p>Your route summary and driver schedule will appear here after you plan a trip.</p>
              </div>
            )}
          </section>
        </div>
        <footer className="page-footer">Planning estimates are based on the provided route and cycle hours.</footer>
      </main>
    </div>
  )
}

export default App

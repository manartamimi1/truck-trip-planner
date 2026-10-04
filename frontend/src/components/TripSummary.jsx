const format = (value, digits = 1) => Number(value).toFixed(digits)

function TripSummary({ result }) {
  const { route, locations, summary, status, remaining_trip: remainingTrip } = result
  const cycleUsed = summary.ending_cycle_used_hours

  return (
    <div className="summary-stack">
      {status === 'completed' ? (
        <div className="hos-message is-positive" role="status">
          <span className="message-icon" aria-hidden="true">✓</span>
          <div><strong>Trip feasible under provided HOS assumptions</strong><span>Route and driver schedule are ready for review.</span></div>
        </div>
      ) : (
        <div className="hos-message is-warning" role="status">
          <span className="message-icon" aria-hidden="true">!</span>
          <div>
            <strong>Trip cannot be completed with the remaining 70-hour cycle availability.</strong>
            {remainingTrip && <span>{format(remainingTrip.distance_miles, 1)} mi and {format(remainingTrip.driving_hours, 1)} driving hours remain, plus pending trip events.</span>}
          </div>
        </div>
      )}

      <div className="metric-grid">
        <article className="metric-card">
          <span className="metric-label">Total distance</span>
          <strong>{format(route.distance_miles)} <small>mi</small></strong>
          <span className="metric-detail">Driving route</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Driving time</span>
          <strong>{format(route.duration_hours)} <small>h</small></strong>
          <span className="metric-detail">Estimated wheel time</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Total trip time</span>
          <strong>{format(summary.total_elapsed_hours)} <small>h</small></strong>
          <span className="metric-detail">Including stops and rest</span>
        </article>
        <article className="metric-card">
          <span className="metric-label">Cycle used</span>
          <strong>{format(cycleUsed)} <small>/ 70 h</small></strong>
          <span className="metric-detail">At trip completion or limit</span>
        </article>
      </div>

      <section className="route-strip" aria-label="Planned route">
        <span className="route-label">ROUTE</span>
        <div className="route-stops">
          {[locations.current, locations.pickup, locations.dropoff].map((location, index) => (
            <span className="route-stop" key={`${location.name}-${index}`}>
              {index > 0 && <span className="route-arrow" aria-hidden="true">→</span>}
              <span className={`route-dot route-dot-${index}`} aria-hidden="true" />
              <strong>{location.name}</strong>
            </span>
          ))}
        </div>
      </section>
    </div>
  )
}

export default TripSummary

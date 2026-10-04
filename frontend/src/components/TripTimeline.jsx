const EVENT_DETAILS = {
  DRIVING: { label: 'Driving', marker: 'D', className: 'driving' },
  PICKUP: { label: 'Pickup', marker: 'P', className: 'pickup' },
  DROPOFF: { label: 'Dropoff', marker: 'D', className: 'dropoff' },
  BREAK: { label: '30-minute break', marker: 'B', className: 'break' },
  SLEEPER: { label: 'Sleeper rest', marker: 'S', className: 'sleeper' },
  FUEL: { label: 'Fuel stop', marker: 'F', className: 'fuel' },
}

function TripTimeline({ events }) {
  return (
    <section className="panel timeline-panel" aria-labelledby="timeline-title">
      <div className="panel-heading timeline-heading">
        <div>
          <p className="eyebrow">DRIVER SCHEDULE</p>
          <h2 id="timeline-title">Trip timeline</h2>
        </div>
        <span className="event-count">{events.length} events</span>
      </div>
      <ol className="timeline-list">
        {events.map((event, index) => {
          const details = EVENT_DETAILS[event.type] ?? { label: 'Trip event', marker: '•', className: 'other' }
          return (
            <li className={`timeline-item event-${details.className}`} key={`${event.type}-${event.start_hour}-${index}`}>
              <span className="timeline-marker" aria-hidden="true">{details.marker}</span>
              <article className="timeline-card">
                <div className="timeline-main">
                  <div>
                    <h3>{details.label}</h3>
                    <p className="timeline-time">{Number(event.start_hour).toFixed(1)}h <span>–</span> {Number(event.end_hour).toFixed(1)}h</p>
                  </div>
                  <strong className="event-duration">{Number(event.duration_hours).toFixed(1)} <small>h</small></strong>
                </div>
                <div className="timeline-meta">
                  <span>{event.type === 'DRIVING' && event.distance_miles != null
                    ? `${Number(event.distance_miles).toFixed(1)} miles`
                    : event.eld_status === 'ON_DUTY' ? 'On duty' : event.eld_status === 'SLEEPER' ? 'Sleeper berth' : event.eld_status === 'OFF_DUTY' ? 'Off duty' : ''}</span>
                  {event.route_leg && event.type === 'DRIVING' && <span>{event.route_leg === 'current_to_pickup' ? 'Current to pickup' : 'Pickup to dropoff'}</span>}
                </div>
              </article>
            </li>
          )
        })}
      </ol>
    </section>
  )
}

export default TripTimeline

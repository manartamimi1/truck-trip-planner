import { ELD_STATUSES, formatClock } from '../utils/eldLogs.js'

const GRAPH = { width: 1240, height: 286, left: 190, right: 1210, top: 28, bottom: 230 }
const ROW_Y = [54, 108, 162, 216]
const STATUS_ORDER = ['OFF_DUTY', 'SLEEPER_BERTH', 'DRIVING', 'ON_DUTY']

function xAt(hour) {
  return GRAPH.left + (hour / 24) * (GRAPH.right - GRAPH.left)
}

function createStepPath(segments) {
  return segments.reduce((path, segment, index) => {
    const xStart = xAt(segment.start_hour)
    const xEnd = xAt(segment.end_hour)
    const y = ROW_Y[ELD_STATUSES[segment.status].row]
    if (index === 0) return `${path}M ${xStart} ${y} H ${xEnd}`
    const previousY = ROW_Y[ELD_STATUSES[segments[index - 1].status].row]
    return `${path} H ${xStart}${previousY === y ? '' : ` V ${y}`} H ${xEnd}`
  }, '')
}

function formatHours(hours) {
  const safeHours = Math.abs(hours) < 0.00005 ? 0 : hours
  return safeHours.toFixed(1)
}

function DutyGraph({ day }) {
  const stepPath = createStepPath(day.segments)

  return (
    <div className="eld-graph-scroll" role="region" aria-label={`Day ${day.day_number} duty status graph`} tabIndex="0">
      <svg
        className="eld-graph"
        viewBox={`0 0 ${GRAPH.width} ${GRAPH.height}`}
        role="img"
        aria-labelledby={`eld-graph-title-${day.day_number} eld-graph-desc-${day.day_number}`}
      >
        <title id={`eld-graph-title-${day.day_number}`}>{`Day ${day.day_number} 24-hour duty status log`}</title>
        <desc id={`eld-graph-desc-${day.day_number}`}>
          One connected stepped line shows the driver duty status from midnight to midnight.
        </desc>

        {Array.from({ length: 25 }, (_, hour) => {
          const major = hour % 2 === 0
          return (
            <g key={hour}>
              <line
                x1={xAt(hour)} y1={GRAPH.top} x2={xAt(hour)} y2={GRAPH.bottom}
                className={major ? 'eld-grid-major' : 'eld-grid-minor'}
              />
              {major && (
                <text x={xAt(hour)} y="258" className="eld-hour-label" textAnchor="middle">
                  {hour === 0 ? '00' : hour === 12 ? 'Noon / 12' : hour === 24 ? '24' : String(hour)}
                </text>
              )}
            </g>
          )
        })}

        {STATUS_ORDER.map((status) => {
          const row = ELD_STATUSES[status]
          const y = ROW_Y[row.row]
          return (
            <g key={status}>
              <line x1={GRAPH.left} y1={y} x2={GRAPH.right} y2={y} className="eld-row-guide" />
              <circle cx="16" cy={y - 4} r="4" className={`eld-status-dot eld-status-${status.toLowerCase()}`} />
              <text x="29" y={row.row === 3 ? y - 4 : y + 4} className="eld-status-label">
                {status === 'ON_DUTY' ? (
                  <>
                    <tspan x="29">ON DUTY</tspan>
                    <tspan x="29" dy="13" className="eld-status-sublabel">(NOT DRIVING)</tspan>
                  </>
                ) : row.label}
              </text>
            </g>
          )
        })}

        {stepPath && <path d={stepPath} className="eld-duty-line" />}
        <line x1={GRAPH.left} y1={GRAPH.top} x2={GRAPH.left} y2={GRAPH.bottom} className="eld-axis-edge" />
        <line x1={GRAPH.right} y1={GRAPH.top} x2={GRAPH.right} y2={GRAPH.bottom} className="eld-axis-edge" />
      </svg>
    </div>
  )
}

function ELDLogSheet({ day }) {
  const rows = [
    ['OFF_DUTY', 'Off Duty'],
    ['SLEEPER_BERTH', 'Sleeper'],
    ['DRIVING', 'Driving'],
    ['ON_DUTY', 'On Duty'],
  ]

  return (
    <article className="eld-sheet panel" aria-labelledby={`eld-day-title-${day.day_number}`}>
      <header className="eld-sheet-heading">
        <div>
          <p className="eyebrow">TRIP HOURS {day.trip_hour_start}–{day.trip_hour_end}</p>
          <h3 id={`eld-day-title-${day.day_number}`}>Day {day.day_number}</h3>
        </div>
        <span className="eld-period-label">24-hour log</span>
      </header>

      <DutyGraph day={day} />

      <div className="eld-details-grid">
        <section className="eld-totals" aria-labelledby={`eld-totals-title-${day.day_number}`}>
          <h4 id={`eld-totals-title-${day.day_number}`}>Daily totals</h4>
          <dl>
            {rows.map(([key, label]) => (
              <div className="eld-total-row" key={key}>
                <dt><i className={`eld-total-dot eld-status-${key.toLowerCase()}`} />{label}</dt>
                <dd>{formatHours(day.totals[key])} h</dd>
              </div>
            ))}
            <div className="eld-total-row eld-total-final">
              <dt>Total</dt>
              <dd>{formatHours(day.total_hours)} h</dd>
            </div>
          </dl>
        </section>

        <section className="eld-remarks" aria-labelledby={`eld-remarks-title-${day.day_number}`}>
          <h4 id={`eld-remarks-title-${day.day_number}`}>Remarks / events</h4>
          {day.remarks.length ? (
            <ul>
              {day.remarks.map((remark) => (
                <li key={`${remark.time}-${remark.label}`}>
                  <time>{remark.time}</time>
                  <span><strong>{remark.label}</strong>{remark.location ? ` — ${remark.location}` : ''}</span>
                </li>
              ))}
            </ul>
          ) : <p className="eld-no-remarks">No additional events this day.</p>}
        </section>
      </div>
      <p className="eld-assumption">Time after trip completion is shown as Off Duty; post-trip activity was not provided.</p>
    </article>
  )
}

export default ELDLogSheet

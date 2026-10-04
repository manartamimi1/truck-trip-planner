import { useMemo } from 'react'
import { createEldLogs } from '../utils/eldLogs.js'
import ELDLogSheet from './ELDLogSheet.jsx'

function ELDLogs({ result }) {
  const logData = useMemo(
    () => {
      try {
        return { days: createEldLogs(result.timeline, result.summary.total_elapsed_hours, result.locations) }
      } catch (error) {
        return { error }
      }
    },
    [result],
  )
  const { days = [] } = logData

  if (logData.error) {
    return (
      <section className="eld-logs-section" aria-labelledby="eld-logs-title">
        <div className="eld-logs-heading">
          <div><p className="eyebrow">DRIVER LOGS</p><h2 id="eld-logs-title">Daily ELD Logs</h2></div>
        </div>
        <p className="eld-data-warning" role="status">
          ELD logs are unavailable because the HOS timeline does not align with the reported trip duration.
        </p>
      </section>
    )
  }

  if (!days.length) return null

  return (
    <section className="eld-logs-section" aria-labelledby="eld-logs-title">
      <div className="eld-logs-heading">
        <div>
          <p className="eyebrow">DRIVER LOGS</p>
          <h2 id="eld-logs-title">Daily ELD Logs</h2>
        </div>
        <span>{days.length} {days.length === 1 ? 'sheet' : 'sheets'}</span>
      </div>
      <div className="eld-sheets">
        {days.map((day) => <ELDLogSheet key={day.day_number} day={day} />)}
      </div>
    </section>
  )
}

export default ELDLogs

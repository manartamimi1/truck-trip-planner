const HOURS_PER_DAY = 24

export const ELD_STATUSES = {
  OFF_DUTY: { label: 'OFF DUTY', row: 0 },
  SLEEPER_BERTH: { label: 'SLEEPER BERTH', row: 1 },
  DRIVING: { label: 'DRIVING', row: 2 },
  ON_DUTY: { label: 'ON DUTY (NOT DRIVING)', row: 3 },
}

const EVENT_STATUS = {
  DRIVING: 'DRIVING',
  SLEEPER: 'SLEEPER_BERTH',
  BREAK: 'OFF_DUTY',
  PICKUP: 'ON_DUTY',
  DROPOFF: 'ON_DUTY',
  FUEL: 'ON_DUTY',
}

const REMARK_LABEL = {
  PICKUP: 'Pickup',
  DROPOFF: 'Dropoff',
  SLEEPER: 'Sleeper rest',
  BREAK: 'Off-duty break',
  FUEL: 'Fuel stop',
}

const EPSILON = 1e-9

function eventStatus(event) {
  return EVENT_STATUS[event.type] ?? (
    event.eld_status === 'SLEEPER' ? 'SLEEPER_BERTH'
      : event.eld_status === 'OFF_DUTY' ? 'OFF_DUTY'
        : event.eld_status === 'ON_DUTY' ? 'ON_DUTY'
          : null
  )
}

function mergeSegments(segments) {
  return segments.reduce((merged, segment) => {
    if (segment.end_hour - segment.start_hour <= EPSILON) return merged
    const previous = merged.at(-1)
    if (previous && previous.status === segment.status && Math.abs(previous.end_hour - segment.start_hour) <= EPSILON) {
      previous.end_hour = segment.end_hour
      previous.events.push(...segment.events)
    } else {
      merged.push({ ...segment, events: [...segment.events] })
    }
    return merged
  }, [])
}

function makeRemarks(daySegments, locations, dayStart) {
  const seen = new Set()
  return daySegments.flatMap((segment) => segment.events.flatMap(({ event, absoluteStart }) => {
    const label = REMARK_LABEL[event.type]
    if (!label || absoluteStart < dayStart - EPSILON || absoluteStart >= dayStart + HOURS_PER_DAY - EPSILON) return []
    const key = `${event.type}-${absoluteStart}`
    if (seen.has(key)) return []
    seen.add(key)
    const locationKey = event.type === 'PICKUP' ? 'pickup' : event.type === 'DROPOFF' ? 'dropoff' : null
    const locationName = locationKey ? locations?.[locationKey]?.name : null
    return [{
      hour: absoluteStart - dayStart,
      time: formatClock(absoluteStart - dayStart),
      label,
      location: locationName || '',
    }]
  })).sort((first, second) => first.hour - second.hour)
}

export function formatClock(hour) {
  const minutes = Math.round(hour * 60)
  const hours = Math.floor(minutes / 60)
  return `${String(hours).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`
}

/** Convert an elapsed-hour HOS timeline into full 24-hour display sheets. */
export function createEldLogs(timeline, totalElapsedHours, locations = {}) {
  if (!Array.isArray(timeline)) throw new TypeError('Trip timeline must be an array.')
  const elapsed = Number(totalElapsedHours)
  if (!Number.isFinite(elapsed) || elapsed < 0) throw new TypeError('Trip elapsed hours must be a non-negative number.')
  if (elapsed === 0) return []

  const chronologicalEvents = timeline.map((event) => {
    const start = Number(event.start_hour)
    const end = Number(event.end_hour)
    const status = eventStatus(event)
    if (!Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end < start || !status) {
      throw new TypeError(`Invalid or unsupported HOS timeline event: ${event.type ?? 'unknown'}.`)
    }
    return { event, start, end, status }
  }).sort((first, second) => first.start - second.start)

  let coveredUntil = 0
  chronologicalEvents.forEach(({ event, start, end }) => {
    if (Math.abs(start - coveredUntil) > EPSILON) {
      throw new Error(`HOS timeline has an unexpected gap or overlap before ${event.type}.`)
    }
    coveredUntil = end
  })
  if (Math.abs(coveredUntil - elapsed) > EPSILON) {
    throw new Error('HOS timeline end does not match the reported trip duration.')
  }

  const dayCount = Math.ceil(elapsed / HOURS_PER_DAY)
  const days = Array.from({ length: dayCount }, (_, index) => ({ index, segments: [], remarks: [] }))

  chronologicalEvents.forEach(({ event, start, end, status }) => {
    let cursor = Math.max(0, start)
    const eventEnd = Math.min(elapsed, end)
    while (cursor < eventEnd - EPSILON) {
      const dayIndex = Math.floor(cursor / HOURS_PER_DAY)
      const dayStart = dayIndex * HOURS_PER_DAY
      const sliceEnd = Math.min(eventEnd, dayStart + HOURS_PER_DAY)
      const day = days[dayIndex]
      if (!day || sliceEnd <= cursor) break
      day.segments.push({
        start_hour: cursor - dayStart,
        end_hour: sliceEnd - dayStart,
        status,
        events: [{ event, absoluteStart: start }],
      })
      cursor = sliceEnd
    }
  })

  return days.map((day) => {
    const dayStart = day.index * HOURS_PER_DAY
    const tripEnd = Math.min(elapsed - dayStart, HOURS_PER_DAY)
    const completed = day.segments.sort((a, b) => a.start_hour - b.start_hour)
    if (tripEnd < HOURS_PER_DAY - EPSILON) {
      // Only time after the actual reported trip completion is assumed off duty.
      completed.push({ start_hour: tripEnd, end_hour: HOURS_PER_DAY, status: 'OFF_DUTY', events: [] })
    }

    const segments = mergeSegments(completed)
    const totals = { OFF_DUTY: 0, SLEEPER_BERTH: 0, DRIVING: 0, ON_DUTY: 0 }
    segments.forEach(({ status, start_hour, end_hour }) => {
      totals[status] += end_hour - start_hour
    })

    // Keep the per-status sum stable against floating point noise while preserving
    // the 24-hour sheet invariant.
    const difference = HOURS_PER_DAY - Object.values(totals).reduce((sum, value) => sum + value, 0)
    if (Math.abs(difference) < 1e-7) {
      const target = totals.OFF_DUTY > 0 ? 'OFF_DUTY' : (segments.at(-1)?.status ?? 'OFF_DUTY')
      totals[target] += difference
    }

    return {
      day_number: day.index + 1,
      trip_hour_start: dayStart,
      trip_hour_end: dayStart + HOURS_PER_DAY,
      segments,
      totals,
      total_hours: Object.values(totals).reduce((sum, value) => sum + value, 0),
      remarks: makeRemarks(segments, locations, dayStart),
    }
  })
}

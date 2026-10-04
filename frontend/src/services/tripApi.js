const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL
const API_BASE_URL = (configuredBaseUrl || 'http://127.0.0.1:8000').replace(/\/$/, '')

function readableError(payload, statusCode) {
  const fieldLabels = {
    current_location: 'Current location',
    pickup_location: 'Pickup location',
    dropoff_location: 'Dropoff location',
    current_cycle_used: 'Current cycle used',
  }
  if (typeof payload?.detail === 'string') {
    const geocodingFailure = payload.detail.match(/^Geocoding service is unavailable while resolving ([a-z_]+)\.$/)
    if (geocodingFailure) {
      const locationLabel = fieldLabels[geocodingFailure[1]]?.toLowerCase() ?? 'the requested location'
      return `The geocoding service is temporarily unavailable while looking up ${locationLabel}. Please try again.`
    }
    if (payload.detail === 'Routing service is unavailable.') {
      return 'The routing service is temporarily unavailable. Please try again.'
    }
    return payload.detail
  }

  if (payload && typeof payload === 'object') {
    const messages = Object.entries(payload)
      .filter(([key]) => fieldLabels[key])
      .map(([key, value]) => `${fieldLabels[key]}: ${Array.isArray(value) ? value.join(' ') : String(value)}`)
    if (messages.length) return messages.join(' ')
  }

  if (statusCode === 502) return 'A routing or geocoding service is temporarily unavailable. Please try again.'
  if (statusCode >= 500) return 'The trip planner could not complete this request. Please try again.'
  return 'The trip request could not be processed. Check the entered details and try again.'
}

export async function planTrip(data) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/trips/plan/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    })
  } catch {
    throw new Error('Unable to connect to the trip planning service. Check that the backend is running.')
  }

  let payload
  try {
    payload = await response.json()
  } catch {
    payload = null
  }

  if (!response.ok) throw new Error(readableError(payload, response.status))
  return payload
}

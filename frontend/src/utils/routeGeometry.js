const EARTH_RADIUS_MILES = 3958.7613

function isCoordinatePair(value) {
  return (
    Array.isArray(value) &&
    value.length >= 2 &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1]) &&
    Math.abs(value[0]) <= 180 &&
    Math.abs(value[1]) <= 90
  )
}

function haversineMiles(first, second) {
  const toRadians = (degrees) => (degrees * Math.PI) / 180
  const [firstLongitude, firstLatitude] = first
  const [secondLongitude, secondLatitude] = second
  const latitudeDelta = toRadians(secondLatitude - firstLatitude)
  const longitudeDelta = toRadians(secondLongitude - firstLongitude)
  const firstLatitudeRadians = toRadians(firstLatitude)
  const secondLatitudeRadians = toRadians(secondLatitude)
  const haversine =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(firstLatitudeRadians) *
      Math.cos(secondLatitudeRadians) *
      Math.sin(longitudeDelta / 2) ** 2
  return 2 * EARTH_RADIUS_MILES * Math.asin(Math.sqrt(Math.min(1, haversine)))
}

/** Build a cumulative-distance lookup for a GeoJSON LineString. */
export function measureLineString(geometry, routeDistanceMiles) {
  if (
    geometry?.type !== 'LineString' ||
    !Array.isArray(geometry.coordinates) ||
    geometry.coordinates.length < 2 ||
    !geometry.coordinates.every(isCoordinatePair)
  ) {
    throw new Error('Route geometry is not a valid GeoJSON LineString.')
  }

  const coordinates = geometry.coordinates.map(([longitude, latitude]) => [longitude, latitude])
  const cumulativeMiles = [0]
  for (let index = 1; index < coordinates.length; index += 1) {
    cumulativeMiles.push(
      cumulativeMiles[index - 1] + haversineMiles(coordinates[index - 1], coordinates[index]),
    )
  }

  const geometryDistanceMiles = cumulativeMiles.at(-1)
  const referenceDistance = Number(routeDistanceMiles)
  const sourceDistanceMiles = Number.isFinite(referenceDistance) && referenceDistance > 0
    ? referenceDistance
    : geometryDistanceMiles

  function coordinateAtDistance(distanceMiles) {
    if (!Number.isFinite(distanceMiles) || distanceMiles < 0) return null
    if (distanceMiles <= 0) return [coordinates[0][1], coordinates[0][0]]
    if (distanceMiles >= sourceDistanceMiles) {
      const last = coordinates.at(-1)
      return [last[1], last[0]]
    }

    // Event distances are measured with OSRM's route distance. Scale them to
    // the measured GeoJSON length to account for small geometry/road-distance differences.
    const targetMiles = (distanceMiles / sourceDistanceMiles) * geometryDistanceMiles
    let low = 1
    let high = cumulativeMiles.length - 1
    while (low < high) {
      const middle = Math.floor((low + high) / 2)
      if (cumulativeMiles[middle] < targetMiles) low = middle + 1
      else high = middle
    }

    const endIndex = low
    const segmentStartMiles = cumulativeMiles[endIndex - 1]
    const segmentMiles = cumulativeMiles[endIndex] - segmentStartMiles
    const fraction = segmentMiles === 0 ? 0 : (targetMiles - segmentStartMiles) / segmentMiles
    const start = coordinates[endIndex - 1]
    const end = coordinates[endIndex]
    return [
      start[1] + (end[1] - start[1]) * fraction,
      start[0] + (end[0] - start[0]) * fraction,
    ]
  }

  return {
    latLngs: coordinates.map(([longitude, latitude]) => [latitude, longitude]),
    geometryDistanceMiles,
    coordinateAtDistance,
  }
}

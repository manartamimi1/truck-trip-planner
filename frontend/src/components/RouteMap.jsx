import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import { measureLineString } from '../utils/routeGeometry.js'

const PRIMARY_LOCATIONS = [
  { key: 'current', label: 'Current location', code: 'C', className: 'current' },
  { key: 'pickup', label: 'Pickup', code: 'P', className: 'pickup' },
  { key: 'dropoff', label: 'Dropoff', code: 'D', className: 'dropoff' },
]

const HOS_STOPS = {
  BREAK: { label: 'Required break', code: 'B', className: 'break', status: 'Off duty' },
  SLEEPER: { label: 'Sleeper rest', code: 'S', className: 'sleeper', status: 'HOS reset' },
  FUEL: { label: 'Fuel stop', code: 'F', className: 'fuel', status: 'On duty' },
}

function makeIcon(code, className, size) {
  const [width, height] = size
  const primary = className !== 'break' && className !== 'sleeper' && className !== 'fuel'
  return L.divIcon({
    className: 'truck-map-icon',
    html: `<span class="map-pin map-pin-${className}${primary ? ' map-pin-primary' : ''}" role="img" aria-label="${code}"><span>${code}</span></span>`,
    iconSize: size,
    iconAnchor: [width / 2, primary ? height - 2 : height / 2],
    popupAnchor: [0, primary ? -height + 5 : -height / 2],
  })
}

const primaryIcons = Object.fromEntries(
  PRIMARY_LOCATIONS.map(({ code, className }) => [className, makeIcon(code, className, [34, 40])]),
)
const stopIcons = Object.fromEntries(
  Object.values(HOS_STOPS).map(({ code, className }) => [className, makeIcon(code, className, [28, 28])]),
)

function validLocation(location) {
  return (
    Number.isFinite(location?.latitude) &&
    Number.isFinite(location?.longitude) &&
    Math.abs(location.latitude) <= 90 &&
    Math.abs(location.longitude) <= 180
  )
}

function formatDuration(hours) {
  const minutes = Math.round(Number(hours) * 60)
  if (!Number.isFinite(minutes) || minutes < 0) return 'Duration unavailable'
  if (minutes > 0 && minutes % 60 === 0) {
    const durationHours = minutes / 60
    return `${durationHours} ${durationHours === 1 ? 'hour' : 'hours'}`
  }
  if (minutes > 0) return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'}`
  return 'Less than a minute'
}

function FitRouteBounds({ boundsPoints }) {
  const map = useMap()

  useEffect(() => {
    if (!boundsPoints.length) return undefined

    let frame = 0
    let active = true
    const bounds = L.latLngBounds(boundsPoints)
    const container = map.getContainer()

    const fitRoute = () => {
      frame = 0
      if (!active || !container.isConnected) return
      const { x: width, y: height } = map.getSize()
      if (!width || !height) return

      map.invalidateSize({ pan: false, debounceMoveend: true })
      map.fitBounds(bounds, {
        padding: [32, 32],
        maxZoom: 11,
        animate: false,
      })
    }

    const scheduleFit = () => {
      if (!frame) frame = requestAnimationFrame(fitRoute)
    }

    const resizeObserver = typeof ResizeObserver === 'undefined'
      ? null
      : new ResizeObserver(scheduleFit)
    resizeObserver?.observe(container)
    map.whenReady(scheduleFit)
    window.addEventListener('resize', scheduleFit)
    scheduleFit()

    return () => {
      active = false
      if (frame) cancelAnimationFrame(frame)
      resizeObserver?.disconnect()
      window.removeEventListener('resize', scheduleFit)
    }
  }, [map, boundsPoints])

  return null
}

function buildMapData(result) {
  const measuredRoute = measureLineString(result?.route?.geometry, result?.route?.distance_miles)
  const locations = PRIMARY_LOCATIONS.map((definition) => {
    const location = result.locations?.[definition.key]
    if (!validLocation(location)) throw new Error('Trip location coordinates are unavailable.')
    return {
      ...definition,
      name: location.name,
      position: [location.latitude, location.longitude],
    }
  })

  const stops = (result.timeline ?? []).flatMap((event, index) => {
    const details = HOS_STOPS[event.type]
    if (!details) return []
    const distance = Number(event.route_distance_miles)
    const position = measuredRoute.coordinateAtDistance(distance)
    if (!position) return []
    return [{ ...details, event, position, key: `${event.type}-${event.start_hour}-${index}` }]
  })

  return {
    ...measuredRoute,
    locations,
    stops,
    boundsPoints: [...measuredRoute.latLngs, ...locations.map(({ position }) => position)],
  }
}

function RouteMap({ result }) {
  const mapData = useMemo(() => {
    try {
      return buildMapData(result)
    } catch {
      return null
    }
  }, [result])

  if (!mapData) {
    return (
      <div className="map-unavailable" role="status">
        <strong>Map unavailable for this route</strong>
        <span>The trip summary and driver timeline are still available.</span>
      </div>
    )
  }

  return (
    <section className="route-map-panel" aria-label="Interactive route map">
      <div className="map-panel-heading">
        <div>
          <p className="eyebrow">ROUTE VISUALIZATION</p>
          <h3>Driving route and stops</h3>
        </div>
        <span className="map-legend" aria-label="Map marker legend">
          <span><i className="legend-primary" />Locations</span>
          <span><i className="legend-hos" />HOS / fuel stops</span>
        </span>
      </div>
      <div className="route-map-frame">
        <MapContainer
          className="route-map"
          center={mapData.latLngs[0]}
          zoom={6}
          scrollWheelZoom
        >
          <FitRouteBounds boundsPoints={mapData.boundsPoints} />
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <Polyline positions={mapData.latLngs} pathOptions={{ color: '#176b68', weight: 5, opacity: 0.82 }} />

          {mapData.locations.map((location) => (
            <Marker key={location.key} position={location.position} icon={primaryIcons[location.className]}>
              <Popup>
                <strong>{location.label}</strong>
                <br />
                <span>{location.name}</span>
              </Popup>
            </Marker>
          ))}

          {mapData.stops.map((stop) => (
            <Marker key={stop.key} position={stop.position} icon={stopIcons[stop.className]}>
              <Popup>
                <strong>{stop.label}</strong>
                <br />
                <span>{formatDuration(stop.event.duration_hours)}</span>
                <br />
                <span>{stop.status}</span>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>
      <p className="map-attribution-note">Route geometry and stop positions are approximate. Map tiles &copy; OpenStreetMap contributors.</p>
    </section>
  )
}

export default RouteMap

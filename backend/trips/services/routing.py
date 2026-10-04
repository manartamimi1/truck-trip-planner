import requests


OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
REQUEST_TIMEOUT_SECONDS = 20


class RoutingError(Exception):
    """Raised when OSRM cannot calculate or return a usable route."""


def get_driving_route(locations):
    """Get a driving route through latitude/longitude locations in given order."""
    coordinates = ";".join(
        f"{location['longitude']},{location['latitude']}" for location in locations
    )
    try:
        response = requests.get(
            f"{OSRM_ROUTE_URL}/{coordinates}",
            params={"overview": "full", "geometries": "geojson", "steps": "false"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RoutingError("OSRM request failed or returned invalid JSON.") from exc

    if not isinstance(data, dict):
        raise RoutingError("OSRM returned an invalid route response.")
    routes = data.get("routes")
    if data.get("code") != "Ok" or not isinstance(routes, list) or not routes:
        message = data.get("message") or data.get("code") or "No route found."
        raise RoutingError(message)

    route = routes[0]
    if not isinstance(route, dict):
        raise RoutingError("OSRM returned an invalid route result.")
    try:
        distance_meters = float(route["distance"])
        duration_seconds = float(route["duration"])
        geometry = route["geometry"]
        if not isinstance(geometry, dict) or geometry.get("type") != "LineString":
            raise ValueError("Expected GeoJSON LineString geometry.")
    except (KeyError, TypeError, ValueError) as exc:
        raise RoutingError("OSRM returned an invalid route result.") from exc

    return {
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "geometry": geometry,
    }

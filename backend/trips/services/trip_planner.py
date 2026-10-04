"""Orchestrate geocoding, route calculation, and the isolated HOS engine."""

from .geocoding import GeocodingError, LocationNotFoundError, geocode_location
from .hos_engine import calculate_hos_timeline
from .routing import RoutingError, get_driving_route


METERS_PER_MILE = 1609.344
SECONDS_PER_HOUR = 3600.0
LOCATION_FIELDS = (
    ("current", "current_location"),
    ("pickup", "pickup_location"),
    ("dropoff", "dropoff_location"),
)
ROUTE_LEG_NAMES = (("current", "pickup"), ("pickup", "dropoff"))


class TripLocationNotFound(Exception):
    """A request location could not be resolved by the geocoding service."""

    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


class TripPlanningUpstreamError(Exception):
    """An upstream geocoding or routing service could not complete the request."""


def create_trip_plan(current_location, pickup_location, dropoff_location, current_cycle_used):
    """Return combined location, route, and HOS data for one trip request."""
    requested_locations = {
        "current_location": current_location,
        "pickup_location": pickup_location,
        "dropoff_location": dropoff_location,
    }
    resolved = {}
    response_locations = {}

    for key, field in LOCATION_FIELDS:
        name = requested_locations[field]
        try:
            coordinates = geocode_location(name)
        except LocationNotFoundError as exc:
            raise TripLocationNotFound(field, str(exc)) from exc
        except GeocodingError as exc:
            raise TripPlanningUpstreamError(
                f"Geocoding service is unavailable while resolving {field}."
            ) from exc
        resolved[key] = coordinates
        response_locations[key] = {
            "name": name,
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
        }

    try:
        osrm_route = get_driving_route(
            [resolved["current"], resolved["pickup"], resolved["dropoff"]]
        )
    except RoutingError as exc:
        raise TripPlanningUpstreamError("Routing service is unavailable.") from exc

    response_legs = [
        {
            "from": from_location,
            "to": to_location,
            "distance_miles": leg["distance_meters"] / METERS_PER_MILE,
            "duration_hours": leg["duration_seconds"] / SECONDS_PER_HOUR,
        }
        for (from_location, to_location), leg in zip(ROUTE_LEG_NAMES, osrm_route["legs"])
    ]
    route = {
        "distance_miles": osrm_route["distance_meters"] / METERS_PER_MILE,
        "duration_hours": osrm_route["duration_seconds"] / SECONDS_PER_HOUR,
        "geometry": osrm_route["geometry"],
        "legs": response_legs,
    }

    hos_result = calculate_hos_timeline(response_legs, current_cycle_used)
    result = {
        "status": hos_result["status"],
        "locations": response_locations,
        "route": route,
        "timeline": hos_result["timeline"],
        "summary": hos_result["summary"],
    }
    if "remaining_trip" in hos_result:
        result["remaining_trip"] = hos_result["remaining_trip"]
    return result

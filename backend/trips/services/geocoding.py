import threading
import time

import requests


NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
REQUEST_TIMEOUT_SECONDS = 10
USER_AGENT = "TruckTripPlanner/1.0 (backend routing service)"
_request_lock = threading.Lock()
_last_request_at = 0.0


class LocationNotFoundError(Exception):
    """Raised when Nominatim has no result for a location."""


class GeocodingError(Exception):
    """Raised when Nominatim cannot be reached or returns unusable data."""


def geocode_location(location_name):
    """Resolve a place name to a latitude/longitude pair using Nominatim."""
    global _last_request_at
    # Nominatim's public service allows at most one request per second per app.
    with _request_lock:
        delay = 1.0 - (time.monotonic() - _last_request_at)
        if delay > 0:
            time.sleep(delay)
        _last_request_at = time.monotonic()
        try:
            response = requests.get(
                NOMINATIM_SEARCH_URL,
                params={"q": location_name, "format": "jsonv2", "limit": 1},
                headers={"User-Agent": USER_AGENT},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            results = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GeocodingError("Nominatim request failed or returned invalid JSON.") from exc

    if not isinstance(results, list) or not results:
        raise LocationNotFoundError(f"Could not find a result for '{location_name}'.")

    try:
        return {"latitude": float(results[0]["lat"]), "longitude": float(results[0]["lon"])}
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Nominatim returned an invalid coordinate result.") from exc

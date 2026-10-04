from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer
from .services.geocoding import LocationNotFoundError, GeocodingError, geocode_location
from .services.routing import RoutingError, get_driving_route


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def route_trip(request):
    serializer = RouteRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    locations = serializer.validated_data

    resolved = {}
    response_locations = {}
    for key, field in (
        ("current", "current_location"),
        ("pickup", "pickup_location"),
        ("dropoff", "dropoff_location"),
    ):
        name = locations[field]
        try:
            coordinates = geocode_location(name)
        except LocationNotFoundError as exc:
            return Response({field: [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
        except GeocodingError as exc:
            return Response(
                {"detail": f"Geocoding service failed for {field}: {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        resolved[key] = coordinates
        response_locations[key] = {
            "name": name,
            "latitude": coordinates["latitude"],
            "longitude": coordinates["longitude"],
        }

    try:
        route = get_driving_route(
            [resolved["current"], resolved["pickup"], resolved["dropoff"]]
        )
    except RoutingError as exc:
        return Response(
            {"detail": f"Routing service failed: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    return Response(
        {
            "locations": response_locations,
            "route": {
                "distance_miles": route["distance_meters"] / 1609.344,
                "duration_hours": route["duration_seconds"] / 3600,
                "geometry": route["geometry"],
            },
        }
    )

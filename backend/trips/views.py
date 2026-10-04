import logging

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .serializers import RouteRequestSerializer, TripPlanRequestSerializer
from .services.geocoding import LocationNotFoundError, GeocodingError, geocode_location
from .services.routing import RoutingError, get_driving_route
from .services.trip_planner import (
    TripLocationNotFound,
    TripPlanningUpstreamError,
    create_trip_plan,
)


logger = logging.getLogger(__name__)


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

    leg_names = [("current", "pickup"), ("pickup", "dropoff")]
    response_legs = [
        {
            "from": from_location,
            "to": to_location,
            "distance_miles": leg["distance_meters"] / 1609.344,
            "duration_hours": leg["duration_seconds"] / 3600,
        }
        for (from_location, to_location), leg in zip(leg_names, route["legs"])
    ]

    return Response(
        {
            "locations": response_locations,
            "route": {
                "distance_miles": route["distance_meters"] / 1609.344,
                "duration_hours": route["duration_seconds"] / 3600,
                "geometry": route["geometry"],
                "legs": response_legs,
            },
        }
    )


@api_view(["POST"])
def plan_trip(request):
    serializer = TripPlanRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    try:
        result = create_trip_plan(**serializer.validated_data)
    except TripLocationNotFound as exc:
        return Response({exc.field: [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)
    except TripPlanningUpstreamError as exc:
        return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)
    except Exception:
        logger.exception("Unexpected error while planning a trip.")
        return Response(
            {"detail": "An unexpected error occurred while planning the trip."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return Response(result, status=status.HTTP_200_OK)

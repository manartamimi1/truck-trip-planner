from unittest.mock import patch

from django.test import SimpleTestCase
from rest_framework.test import APIClient

from .services.geocoding import GeocodingError, LocationNotFoundError
from .services.routing import RoutingError


class TripPlannerEndpointTests(SimpleTestCase):
    url = "/api/trips/plan/"
    payload = {
        "current_location": "Chicago, IL",
        "pickup_location": "Indianapolis, IN",
        "dropoff_location": "Atlanta, GA",
        "current_cycle_used": 15,
    }
    coordinates = {
        "current": {"latitude": 41.8755616, "longitude": -87.6244212},
        "pickup": {"latitude": 39.7683331, "longitude": -86.1583502},
        "dropoff": {"latitude": 33.7544657, "longitude": -84.3898151},
    }
    geometry = {"type": "LineString", "coordinates": [[-87.6, 41.8], [-84.3, 33.7]]}
    osrm_route = {
        "distance_meters": 1100400.0,
        "duration_seconds": 48422.5,
        "geometry": geometry,
        "legs": [
            {"distance_meters": 290722.0, "duration_seconds": 13007.1},
            {"distance_meters": 809678.0, "duration_seconds": 35415.4},
        ],
    }
    hos_result = {
        "status": "completed",
        "timeline": [{"type": "DRIVING", "start_hour": 0.0, "end_hour": 2.0}],
        "summary": {"total_elapsed_hours": 4.0, "ending_cycle_used_hours": 19.0},
    }

    def setUp(self):
        self.client = APIClient()

    def mock_dependencies(self):
        return (
            patch(
                "trips.services.trip_planner.geocode_location",
                side_effect=[self.coordinates[key] for key in ("current", "pickup", "dropoff")],
            ),
            patch("trips.services.trip_planner.get_driving_route", return_value=self.osrm_route),
            patch("trips.services.trip_planner.calculate_hos_timeline", return_value=self.hos_result),
        )

    def test_valid_request_returns_combined_response_and_preserves_order(self):
        geocode_patch, route_patch, hos_patch = self.mock_dependencies()
        with geocode_patch as geocode, route_patch as get_route, hos_patch as hos:
            response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [call.args[0] for call in geocode.call_args_list],
            ["Chicago, IL", "Indianapolis, IN", "Atlanta, GA"],
        )
        get_route.assert_called_once_with(
            [self.coordinates["current"], self.coordinates["pickup"], self.coordinates["dropoff"]]
        )
        self.assertEqual(response.data["status"], "completed")
        self.assertEqual(response.data["locations"]["current"]["name"], "Chicago, IL")
        self.assertEqual(response.data["locations"]["pickup"]["name"], "Indianapolis, IN")
        self.assertEqual(response.data["locations"]["dropoff"]["name"], "Atlanta, GA")
        self.assertEqual(response.data["route"]["geometry"], self.geometry)
        self.assertEqual(len(response.data["route"]["legs"]), 2)
        self.assertEqual(response.data["route"]["legs"][0]["from"], "current")
        self.assertEqual(response.data["route"]["legs"][0]["to"], "pickup")
        self.assertEqual(response.data["route"]["legs"][1]["from"], "pickup")
        self.assertEqual(response.data["route"]["legs"][1]["to"], "dropoff")
        self.assertEqual(response.data["timeline"], self.hos_result["timeline"])
        self.assertEqual(response.data["summary"], self.hos_result["summary"])
        hos.assert_called_once_with(response.data["route"]["legs"], 15.0)

    def test_location_and_cycle_fields_are_required_and_locations_non_blank(self):
        for field in (
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_used",
        ):
            with self.subTest(field=field):
                payload = dict(self.payload)
                del payload[field]
                response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

        for field in ("current_location", "pickup_location", "dropoff_location"):
            with self.subTest(blank_field=field):
                payload = dict(self.payload)
                payload[field] = "   "
                response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

    def test_cycle_must_be_numeric_and_between_zero_and_seventy(self):
        for invalid_value in (-0.01, 70.01, "not numeric", "NaN", "Infinity"):
            with self.subTest(invalid_value=invalid_value):
                payload = dict(self.payload, current_cycle_used=invalid_value)
                response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn("current_cycle_used", response.data)

        for valid_value in (0, 70):
            with self.subTest(valid_value=valid_value):
                payload = dict(self.payload, current_cycle_used=valid_value)
                geocode_patch, route_patch, hos_patch = self.mock_dependencies()
                with geocode_patch, route_patch, hos_patch:
                    response = self.client.post(self.url, payload, format="json")
                self.assertEqual(response.status_code, 200)

    @patch("trips.services.trip_planner.geocode_location", side_effect=LocationNotFoundError("No result."))
    def test_geocoding_location_not_found_returns_400(self, geocode):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_location", response.data)

    @patch("trips.services.trip_planner.geocode_location", side_effect=GeocodingError("Unavailable."))
    def test_geocoding_service_failure_returns_502(self, geocode):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("Unavailable", response.data["detail"])

    @patch("trips.services.trip_planner.geocode_location")
    @patch("trips.services.trip_planner.get_driving_route", side_effect=RoutingError("No route."))
    def test_routing_service_failure_returns_502(self, get_route, geocode):
        geocode.side_effect = [
            self.coordinates["current"],
            self.coordinates["pickup"],
            self.coordinates["dropoff"],
        ]
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 502)

    @patch("trips.services.trip_planner.geocode_location")
    @patch("trips.services.trip_planner.get_driving_route")
    @patch("trips.services.trip_planner.calculate_hos_timeline")
    def test_cycle_limited_plan_is_still_http_200(self, hos, get_route, geocode):
        geocode.side_effect = [
            self.coordinates["current"],
            self.coordinates["pickup"],
            self.coordinates["dropoff"],
        ]
        get_route.return_value = self.osrm_route
        hos.return_value = {
            "status": "cycle_limit_reached",
            "timeline": [{"type": "DRIVING"}],
            "summary": {"ending_cycle_used_hours": 70.0},
            "remaining_trip": {"distance_miles": 10.0},
        }

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "cycle_limit_reached")
        self.assertIn("remaining_trip", response.data)


__all__ = ["TripPlannerEndpointTests"]

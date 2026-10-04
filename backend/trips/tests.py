from unittest.mock import Mock, patch

import requests
from django.test import SimpleTestCase
from rest_framework.test import APIClient

from .services.geocoding import GeocodingError, LocationNotFoundError, geocode_location
from .services.routing import RoutingError, get_driving_route


class RouteEndpointTests(SimpleTestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/trips/route/"
        self.payload = {
            "current_location": "Chicago, IL",
            "pickup_location": "Indianapolis, IN",
            "dropoff_location": "Atlanta, GA",
        }

    def test_requires_non_empty_locations(self):
        response = self.client.post(
            self.url,
            {"current_location": " ", "pickup_location": "Indianapolis, IN"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_location", response.data)
        self.assertIn("dropoff_location", response.data)

    @patch("trips.views.get_driving_route")
    @patch("trips.views.geocode_location")
    def test_geocodes_locations_and_returns_route(self, geocode, get_route):
        geocode.side_effect = [
            {"latitude": 41.8781, "longitude": -87.6298},
            {"latitude": 39.7684, "longitude": -86.1581},
            {"latitude": 33.749, "longitude": -84.388},
        ]
        geometry = {"type": "LineString", "coordinates": [[-87.6298, 41.8781]]}
        get_route.return_value = {
            "distance_meters": 160934.4,
            "duration_seconds": 7200,
            "geometry": geometry,
            "legs": [
                {"distance_meters": 100000, "duration_seconds": 3600},
                {"distance_meters": 60934.4, "duration_seconds": 3600},
            ],
        }

        response = self.client.post(self.url, self.payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["route"]["distance_miles"], 100)
        self.assertEqual(response.data["route"]["duration_hours"], 2)
        self.assertEqual(response.data["route"]["geometry"], geometry)
        self.assertEqual(len(response.data["route"]["legs"]), 2)
        self.assertEqual(
            response.data["route"]["legs"],
            [
                {
                    "from": "current",
                    "to": "pickup",
                    "distance_miles": 100000 / 1609.344,
                    "duration_hours": 1,
                },
                {
                    "from": "pickup",
                    "to": "dropoff",
                    "distance_miles": 60934.4 / 1609.344,
                    "duration_hours": 1,
                },
            ],
        )
        for leg in response.data["route"]["legs"]:
            self.assertIn("distance_miles", leg)
            self.assertIn("duration_hours", leg)
        self.assertEqual(
            [call.args[0] for call in geocode.call_args_list],
            ["Chicago, IL", "Indianapolis, IN", "Atlanta, GA"],
        )
        self.assertEqual(
            get_route.call_args.args[0],
            [
                {"latitude": 41.8781, "longitude": -87.6298},
                {"latitude": 39.7684, "longitude": -86.1581},
                {"latitude": 33.749, "longitude": -84.388},
            ],
        )

    @patch("trips.views.geocode_location", side_effect=LocationNotFoundError("Place not found."))
    def test_unfound_location_returns_field_specific_400(self, geocode):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_location", response.data)

    @patch("trips.views.geocode_location", side_effect=GeocodingError("Service unavailable."))
    def test_geocoding_failure_returns_502(self, geocode):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 502)

    @patch("trips.views.geocode_location", return_value={"latitude": 1, "longitude": 2})
    @patch("trips.views.get_driving_route", side_effect=RoutingError("No route."))
    def test_routing_failure_returns_502(self, get_route, geocode):
        response = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(response.status_code, 502)


class GeocodingServiceTests(SimpleTestCase):
    @patch("trips.services.geocoding.requests.get")
    def test_nominatim_request_and_result(self, get):
        response = Mock()
        response.json.return_value = [{"lat": "41.88", "lon": "-87.63"}]
        get.return_value = response

        self.assertEqual(
            geocode_location("Chicago, IL"),
            {"latitude": 41.88, "longitude": -87.63},
        )
        self.assertEqual(get.call_args.kwargs["params"], {
            "q": "Chicago, IL", "format": "jsonv2", "limit": 1
        })
        self.assertIn("User-Agent", get.call_args.kwargs["headers"])
        self.assertEqual(get.call_args.kwargs["timeout"], 10)

    @patch("trips.services.geocoding.requests.get")
    def test_location_not_found(self, get):
        response = Mock()
        response.json.return_value = []
        get.return_value = response
        with self.assertRaises(LocationNotFoundError):
            geocode_location("Unknown Place")

    @patch("trips.services.geocoding.requests.get", side_effect=requests.Timeout)
    def test_network_error(self, get):
        with self.assertRaises(GeocodingError):
            geocode_location("Chicago, IL")


class RoutingServiceTests(SimpleTestCase):
    @patch("trips.services.routing.requests.get")
    def test_osrm_route_preserves_waypoint_order_and_result(self, get):
        geometry = {"type": "LineString", "coordinates": [[-87.6, 41.8], [-86.1, 39.7]]}
        response = Mock()
        response.json.return_value = {
            "code": "Ok",
            "routes": [{
                "distance": 1000,
                "duration": 720,
                "geometry": geometry,
                "legs": [
                    {"distance": 400, "duration": 300},
                    {"distance": 600, "duration": 420},
                ],
            }],
        }
        get.return_value = response
        locations = [
            {"latitude": 41.8, "longitude": -87.6},
            {"latitude": 39.7, "longitude": -86.1},
            {"latitude": 33.7, "longitude": -84.3},
        ]

        self.assertEqual(
            get_driving_route(locations),
            {
                "distance_meters": 1000,
                "duration_seconds": 720,
                "geometry": geometry,
                "legs": [
                    {"distance_meters": 400, "duration_seconds": 300},
                    {"distance_meters": 600, "duration_seconds": 420},
                ],
            },
        )
        self.assertIn("-87.6,41.8;-86.1,39.7;-84.3,33.7", get.call_args.args[0])
        self.assertEqual(
            get.call_args.kwargs["params"],
            {"overview": "full", "geometries": "geojson", "steps": "false"},
        )

    @patch("trips.services.routing.requests.get")
    def test_osrm_no_route(self, get):
        response = Mock()
        response.json.return_value = {"code": "NoRoute", "message": "No route found"}
        get.return_value = response
        with self.assertRaises(RoutingError):
            get_driving_route([{"latitude": 1, "longitude": 2}] * 3)

    @patch("trips.services.routing.requests.get")
    def test_invalid_osrm_response(self, get):
        response = Mock()
        response.json.return_value = []
        get.return_value = response
        with self.assertRaises(RoutingError):
            get_driving_route([{"latitude": 1, "longitude": 2}] * 3)

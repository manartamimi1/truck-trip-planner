from unittest.mock import patch

from django.test import SimpleTestCase

from .services.hos_engine import (
    FUEL_STOP_DURATION_HOURS,
    calculate_hos_timeline,
)


def leg(origin, destination, distance_miles, duration_hours):
    return {
        "from": origin,
        "to": destination,
        "distance_miles": distance_miles,
        "duration_hours": duration_hours,
    }


def route(first_distance, first_hours, second_distance=0, second_hours=0):
    return [
        leg("current", "pickup", first_distance, first_hours),
        leg("pickup", "dropoff", second_distance, second_hours),
    ]


class HosEngineTests(SimpleTestCase):
    def calculate(self, legs, cycle=0):
        return calculate_hos_timeline(legs, cycle)

    def events_of_type(self, result, event_type):
        return [event for event in result["timeline"] if event["type"] == event_type]

    def test_short_trip_completes_without_break_or_sleeper(self):
        result = self.calculate(route(250, 2.5, 250, 2.5))
        event_types = [event["type"] for event in result["timeline"]]
        self.assertEqual(result["status"], "completed")
        self.assertNotIn("BREAK", event_types)
        self.assertNotIn("SLEEPER", event_types)
        self.assertAlmostEqual(result["summary"]["driving_hours"], 5)

    def test_eight_hours_exactly_does_not_add_unneeded_break(self):
        result = self.calculate(route(400, 8))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.events_of_type(result, "BREAK"), [])
        self.assertAlmostEqual(result["summary"]["driving_hours"], 8)

    def test_nine_hours_driving_requires_qualifying_break(self):
        result = self.calculate(route(450, 9))
        self.assertEqual(
            [event["duration_hours"] for event in self.events_of_type(result, "DRIVING")],
            [8, 1],
        )
        self.assertEqual(self.events_of_type(result, "BREAK")[0]["duration_hours"], 0.5)
        self.assertEqual(result["status"], "completed")

    def test_thirteen_hours_driving_uses_break_then_sleeper(self):
        result = self.calculate(route(650, 13))
        driving_durations = [
            event["duration_hours"] for event in self.events_of_type(result, "DRIVING")
        ]
        self.assertEqual(driving_durations, [8, 3, 2])
        self.assertEqual(
            [event["distance_miles"] for event in self.events_of_type(result, "DRIVING")],
            [400, 150, 100],
        )
        self.assertEqual(len(self.events_of_type(result, "BREAK")), 1)
        self.assertEqual(self.events_of_type(result, "SLEEPER")[0]["duration_hours"], 10)
        self.assertEqual(result["status"], "completed")

    def test_pickup_is_on_duty_and_advances_window_and_cycle_not_drive_clock(self):
        result = self.calculate(route(180, 3, 120, 2), cycle=10)
        pickup = self.events_of_type(result, "PICKUP")[0]
        second_leg_drive = next(
            event for event in self.events_of_type(result, "DRIVING")
            if event["route_leg"] == "pickup_to_dropoff"
        )
        self.assertEqual(pickup["eld_status"], "ON_DUTY")
        self.assertEqual(pickup["duration_hours"], 1)
        self.assertEqual(pickup["start_hour"], 3)
        self.assertEqual(second_leg_drive["start_hour"], 4)
        self.assertEqual(result["summary"]["driving_hours"], 5)
        self.assertEqual(result["summary"]["on_duty_hours"], 2)
        self.assertEqual(result["summary"]["ending_cycle_used_hours"], 17)

    def test_dropoff_is_one_on_duty_hour_after_arrival(self):
        result = self.calculate(route(60, 1.5, 60, 1.5))
        dropoff = self.events_of_type(result, "DROPOFF")[0]
        last_drive = self.events_of_type(result, "DRIVING")[-1]
        self.assertEqual(dropoff["eld_status"], "ON_DUTY")
        self.assertEqual(dropoff["duration_hours"], 1)
        self.assertEqual(dropoff["start_hour"], last_drive["end_hour"])

    @patch("trips.services.hos_engine.FUEL_STOP_DURATION_HOURS", 2.0)
    def test_duty_window_can_require_sleeper_before_eleven_driving_hours(self):
        result = self.calculate(route(1000, 4.5, 2500, 9))
        sleepers = self.events_of_type(result, "SLEEPER")
        self.assertTrue(sleepers)
        self.assertEqual(sleepers[0]["start_hour"], 14)
        drive_before_sleeper = sum(
            event["duration_hours"] for event in self.events_of_type(result, "DRIVING")
            if event["end_hour"] <= sleepers[0]["start_hour"]
        )
        self.assertAlmostEqual(drive_before_sleeper, 9)

    def test_break_does_not_reset_eleven_hour_driving_clock(self):
        result = self.calculate(route(650, 13))
        sleeper = self.events_of_type(result, "SLEEPER")[0]
        drive_before_sleeper = sum(
            event["duration_hours"] for event in self.events_of_type(result, "DRIVING")
            if event["end_hour"] <= sleeper["start_hour"]
        )
        self.assertAlmostEqual(drive_before_sleeper, 11)

    def test_sleeper_resets_driving_and_window_but_not_cycle(self):
        result = self.calculate(route(650, 13), cycle=12)
        sleeper = self.events_of_type(result, "SLEEPER")[0]
        later_drives = [
            event for event in self.events_of_type(result, "DRIVING")
            if event["start_hour"] >= sleeper["end_hour"]
        ]
        self.assertTrue(later_drives)
        self.assertAlmostEqual(sum(event["duration_hours"] for event in later_drives), 2)
        self.assertAlmostEqual(result["summary"]["ending_cycle_used_hours"], 27)

    def test_ten_cycle_hours_available_are_used_without_rest_reset(self):
        result = self.calculate(route(450, 9, 250, 5), cycle=60)
        self.assertEqual(result["status"], "cycle_limit_reached")
        self.assertAlmostEqual(result["summary"]["driving_hours"], 9)
        self.assertAlmostEqual(result["summary"]["on_duty_hours"], 1)
        self.assertEqual(result["summary"]["ending_cycle_used_hours"], 70)
        self.assertEqual(result["summary"]["cycle_hours_used_this_trip"], 10)

    def test_cycle_nearly_exhausted_stops_without_sleeper(self):
        result = self.calculate(route(250, 5, 100, 2), cycle=68)
        self.assertEqual(result["status"], "cycle_limit_reached")
        self.assertAlmostEqual(result["summary"]["driving_hours"], 2)
        self.assertEqual(self.events_of_type(result, "DRIVING")[0]["distance_miles"], 100)
        self.assertEqual(result["summary"]["ending_cycle_used_hours"], 70)
        self.assertEqual(self.events_of_type(result, "SLEEPER"), [])

    def test_cycle_input_must_be_between_zero_and_seventy(self):
        for invalid_cycle in (-0.1, 70.1):
            with self.subTest(invalid_cycle=invalid_cycle), self.assertRaises(ValueError):
                self.calculate(route(10, 1, 10, 1), cycle=invalid_cycle)

    def test_route_and_cycle_inputs_reject_non_finite_or_invalid_values(self):
        with self.assertRaises(ValueError):
            self.calculate(route(10, 1, 10, 1), cycle=float("nan"))
        with self.assertRaises(ValueError):
            self.calculate([leg("current", "pickup", -1, 1), leg("pickup", "dropoff", 1, 1)])

    def test_route_under_one_thousand_miles_has_no_distance_fuel_stop(self):
        result = self.calculate(route(300, 3, 300, 3))
        self.assertEqual(self.events_of_type(result, "FUEL"), [])

    def test_route_over_one_thousand_miles_fuels_at_distance_threshold_on_duty(self):
        result = self.calculate(route(900, 4, 600, 3))
        fuel_events = self.events_of_type(result, "FUEL")
        self.assertEqual(len(fuel_events), 1)
        self.assertEqual(fuel_events[0]["route_distance_miles"], 1000)
        self.assertEqual(fuel_events[0]["duration_hours"], FUEL_STOP_DURATION_HOURS)
        self.assertEqual(fuel_events[0]["eld_status"], "ON_DUTY")
        self.assertEqual(result["summary"]["on_duty_hours"], 2 + FUEL_STOP_DURATION_HOURS)

    def test_two_legs_pickup_and_dropoff_keep_required_order(self):
        result = self.calculate(route(100, 1, 200, 2))
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            [event["type"] for event in result["timeline"]],
            ["DRIVING", "PICKUP", "DRIVING", "DROPOFF"],
        )
        drives = self.events_of_type(result, "DRIVING")
        self.assertEqual(
            [event["route_leg"] for event in drives],
            ["current_to_pickup", "pickup_to_dropoff"],
        )


__all__ = ["HosEngineTests"]

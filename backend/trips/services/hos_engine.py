"""Deterministic property-carrying driver HOS timeline calculation."""

import math
from numbers import Real


# Assessment rules and configurable stop durations.
CYCLE_LIMIT_HOURS = 70.0
DRIVING_LIMIT_HOURS = 11.0
DUTY_WINDOW_HOURS = 14.0
BREAK_INTERVAL_HOURS = 8.0
BREAK_DURATION_HOURS = 0.5
SLEEPER_REST_HOURS = 10.0
PICKUP_DURATION_HOURS = 1.0
DROPOFF_DURATION_HOURS = 1.0
FUEL_INTERVAL_MILES = 1000.0
FUEL_STOP_DURATION_HOURS = 0.5

_EPSILON = 1e-9
_LEG_NAMES = ("current_to_pickup", "pickup_to_dropoff")
_LEG_ENDPOINTS = (("current", "pickup"), ("pickup", "dropoff"))


def _finite_number(value, label, *, minimum=0.0):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{label} must be a finite number.")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{label} must be a finite number greater than or equal to {minimum}.")
    return number


def _validate_route_legs(route_legs):
    if not isinstance(route_legs, (list, tuple)) or len(route_legs) != 2:
        raise ValueError("route_legs must contain current-to-pickup and pickup-to-dropoff legs.")

    validated = []
    for index, (leg, expected_endpoints) in enumerate(zip(route_legs, _LEG_ENDPOINTS)):
        if not isinstance(leg, dict):
            raise ValueError("Each route leg must be an object.")
        if "from" in leg and "to" in leg and (leg["from"], leg["to"]) != expected_endpoints:
            raise ValueError("Route legs must be ordered current-to-pickup, then pickup-to-dropoff.")

        distance = _finite_number(leg.get("distance_miles"), "distance_miles")
        duration = _finite_number(leg.get("duration_hours"), "duration_hours")
        if (distance > 0) != (duration > 0):
            raise ValueError("A route leg must have both positive distance and duration, or both zero.")
        validated.append(
            {
                "name": _LEG_NAMES[index],
                "distance_miles": distance,
                "duration_hours": duration,
            }
        )
    return validated


def _summarize(timeline, current_cycle_used_hours, total_elapsed_hours):
    driving_hours = sum(event["duration_hours"] for event in timeline if event["type"] == "DRIVING")
    on_duty_hours = sum(
        event["duration_hours"] for event in timeline if event["eld_status"] == "ON_DUTY"
    )
    off_duty_hours = sum(
        event["duration_hours"] for event in timeline if event["eld_status"] == "OFF_DUTY"
    )
    sleeper_hours = sum(event["duration_hours"] for event in timeline if event["type"] == "SLEEPER")
    distance_miles = sum(event.get("distance_miles", 0.0) for event in timeline)
    cycle_hours_used_this_trip = driving_hours + on_duty_hours
    return {
        "driving_hours": driving_hours,
        "on_duty_hours": on_duty_hours,
        "off_duty_hours": off_duty_hours,
        "sleeper_hours": sleeper_hours,
        "total_elapsed_hours": total_elapsed_hours,
        "distance_miles": distance_miles,
        "cycle_hours_used_this_trip": cycle_hours_used_this_trip,
        "ending_cycle_used_hours": current_cycle_used_hours + cycle_hours_used_this_trip,
    }


def _remaining_trip(legs, leg_index, leg_elapsed_hours, leg_distance_miles,
                    pickup_complete, dropoff_complete, fuel_pending=False):
    remaining_legs = []
    for index in range(leg_index, len(legs)):
        leg = legs[index]
        if index == leg_index:
            distance = max(0.0, leg["distance_miles"] - leg_distance_miles)
            duration = max(0.0, leg["duration_hours"] - leg_elapsed_hours)
        else:
            distance = leg["distance_miles"]
            duration = leg["duration_hours"]
        if distance > _EPSILON or duration > _EPSILON:
            remaining_legs.append(
                {"route_leg": leg["name"], "distance_miles": distance, "driving_hours": duration}
            )

    pending_events = []
    if fuel_pending:
        pending_events.append("FUEL")
    if not pickup_complete:
        pending_events.append("PICKUP")
    if not dropoff_complete:
        pending_events.append("DROPOFF")

    return {
        "remaining_legs": remaining_legs,
        "distance_miles": sum(leg["distance_miles"] for leg in remaining_legs),
        "driving_hours": sum(leg["driving_hours"] for leg in remaining_legs),
        "pending_events": pending_events,
    }


class _TimelineBuilder:
    """Mutable execution state for one deterministic trip calculation."""

    def __init__(self, legs, current_cycle_used_hours):
        self.legs = legs
        self.initial_cycle_used_hours = current_cycle_used_hours
        self.cycle_used_hours = current_cycle_used_hours
        self.timeline = []
        self.elapsed = 0.0
        self.total_distance_driven = 0.0
        self.distance_since_fuel = 0.0
        self.driving_since_rest = 0.0
        self.driving_since_break = 0.0
        self.duty_window_elapsed = 0.0
        self.pickup_complete = False
        self.dropoff_complete = False
        self.halted = None
        self.leg_elapsed_hours = 0.0
        self.leg_distance_miles = 0.0

    def cycle_remaining(self):
        return max(0.0, CYCLE_LIMIT_HOURS - self.cycle_used_hours)

    def location_metadata(self, index):
        leg = self.legs[index]
        if leg["distance_miles"] > 0:
            progress = self.leg_distance_miles / leg["distance_miles"]
        elif leg["duration_hours"] > 0:
            progress = self.leg_elapsed_hours / leg["duration_hours"]
        else:
            progress = 0.0 if index == 0 else 1.0
        return {
            "route_leg": leg["name"],
            "leg_progress": min(1.0, max(0.0, progress)),
            "route_distance_miles": self.total_distance_driven,
        }

    def add_event(self, event_type, eld_status, duration, index, *, distance_miles=None, **extra):
        event = {
            "type": event_type,
            "eld_status": eld_status,
            "start_hour": self.elapsed,
            "end_hour": self.elapsed + duration,
            "duration_hours": duration,
            **self.location_metadata(index),
        }
        if distance_miles is not None:
            event["distance_miles"] = distance_miles
        if event_type == "DRIVING":
            event["route_distance_start_miles"] = self.total_distance_driven
            event["route_distance_end_miles"] = self.total_distance_driven + distance_miles
            event["route_distance_miles"] = event["route_distance_end_miles"]
        event.update(extra)
        self.timeline.append(event)
        self.elapsed += duration

        if event_type == "DRIVING":
            self.cycle_used_hours += duration
            self.duty_window_elapsed += duration
            self.driving_since_rest += duration
            self.driving_since_break += duration
            self.total_distance_driven += distance_miles or 0.0
            self.distance_since_fuel += distance_miles or 0.0
        elif eld_status == "ON_DUTY":
            self.cycle_used_hours += duration
            self.duty_window_elapsed += duration
            if duration >= BREAK_DURATION_HOURS:
                self.driving_since_break = 0.0
        elif event_type == "BREAK":
            # A normal break advances the 14-hour window but does not reset it.
            self.duty_window_elapsed += duration
            self.driving_since_break = 0.0
        elif event_type == "SLEEPER":
            self.driving_since_rest = 0.0
            self.driving_since_break = 0.0
            self.duty_window_elapsed = 0.0

    def halt_for_cycle(self, index, *, fuel_pending=False):
        self.halted = _remaining_trip(
            self.legs,
            index,
            self.leg_elapsed_hours,
            self.leg_distance_miles,
            self.pickup_complete,
            self.dropoff_complete,
            fuel_pending=fuel_pending,
        )

    def add_fuel(self, index):
        if self.cycle_remaining() < FUEL_STOP_DURATION_HOURS:
            self.halt_for_cycle(index, fuel_pending=True)
            return False
        self.add_event(
            "FUEL",
            "ON_DUTY",
            FUEL_STOP_DURATION_HOURS,
            index,
            distance_since_last_fuel_miles=FUEL_INTERVAL_MILES,
        )
        self.distance_since_fuel = max(0.0, self.distance_since_fuel - FUEL_INTERVAL_MILES)
        return True

    def drive_leg(self, index):
        leg = self.legs[index]
        self.leg_elapsed_hours = 0.0
        self.leg_distance_miles = 0.0

        while (
            self.leg_elapsed_hours < leg["duration_hours"] - _EPSILON
            or self.distance_since_fuel >= FUEL_INTERVAL_MILES - _EPSILON
        ):
            if self.distance_since_fuel >= FUEL_INTERVAL_MILES - _EPSILON:
                if not self.add_fuel(index):
                    return False
                continue

            remaining_leg_hours = leg["duration_hours"] - self.leg_elapsed_hours
            if remaining_leg_hours <= _EPSILON:
                break
            if self.cycle_remaining() <= _EPSILON:
                self.halt_for_cycle(index)
                return False

            if (
                self.driving_since_rest >= DRIVING_LIMIT_HOURS - _EPSILON
                or self.duty_window_elapsed >= DUTY_WINDOW_HOURS - _EPSILON
            ):
                self.add_event(
                    "SLEEPER", "SLEEPER", SLEEPER_REST_HOURS, index
                )
                continue

            if self.driving_since_break >= BREAK_INTERVAL_HOURS - _EPSILON:
                self.add_event("BREAK", "OFF_DUTY", BREAK_DURATION_HOURS, index)
                continue

            available_to_drive = min(
                remaining_leg_hours,
                DRIVING_LIMIT_HOURS - self.driving_since_rest,
                DUTY_WINDOW_HOURS - self.duty_window_elapsed,
                BREAK_INTERVAL_HOURS - self.driving_since_break,
                self.cycle_remaining(),
            )
            miles_per_hour = leg["distance_miles"] / leg["duration_hours"]
            hours_to_fuel = (
                (FUEL_INTERVAL_MILES - self.distance_since_fuel) / miles_per_hour
                if miles_per_hour > 0
                else math.inf
            )
            drive_duration = min(available_to_drive, hours_to_fuel)
            if drive_duration <= 0:
                self.halt_for_cycle(index)
                return False

            progress_start = (
                self.leg_distance_miles / leg["distance_miles"] if leg["distance_miles"] else 0.0
            )
            if drive_duration >= remaining_leg_hours - _EPSILON:
                drive_distance = leg["distance_miles"] - self.leg_distance_miles
                drive_duration = remaining_leg_hours
            else:
                drive_distance = miles_per_hour * drive_duration
            self.leg_elapsed_hours += drive_duration
            self.leg_distance_miles += drive_distance
            progress_end = (
                self.leg_distance_miles / leg["distance_miles"] if leg["distance_miles"] else 1.0
            )
            self.add_event(
                "DRIVING",
                "DRIVING",
                drive_duration,
                index,
                distance_miles=drive_distance,
                leg_progress_start=min(1.0, max(0.0, progress_start)),
                leg_progress_end=min(1.0, max(0.0, progress_end)),
            )
            if abs(self.distance_since_fuel - FUEL_INTERVAL_MILES) <= _EPSILON:
                self.distance_since_fuel = FUEL_INTERVAL_MILES
        return True

    def perform_pickup_or_dropoff(self, index):
        if index == 0:
            event_type = "PICKUP"
            duration = PICKUP_DURATION_HOURS
        else:
            event_type = "DROPOFF"
            duration = DROPOFF_DURATION_HOURS
        if self.cycle_remaining() < duration:
            self.halt_for_cycle(index)
            return False

        self.add_event(event_type, "ON_DUTY", duration, index)
        if event_type == "PICKUP":
            self.pickup_complete = True
        else:
            self.dropoff_complete = True
        return True

    def run(self):
        for index in range(len(self.legs)):
            if not self.drive_leg(index):
                break
            if not self.perform_pickup_or_dropoff(index):
                break

        summary = _summarize(
            self.timeline, self.initial_cycle_used_hours, self.elapsed
        )
        result = {
            "status": "cycle_limit_reached" if self.halted is not None else "completed",
            "timeline": self.timeline,
            "summary": summary,
        }
        if self.halted is not None:
            result["remaining_trip"] = self.halted
        return result


def calculate_hos_timeline(route_legs, current_cycle_used_hours):
    """Build a trip timeline from its two routed legs and the driver's cycle use.

    Input legs contain ``from``, ``to``, ``distance_miles`` and ``duration_hours``.
    The function performs no network access and returns unrounded values.
    """
    legs = _validate_route_legs(route_legs)
    cycle_used = _finite_number(current_cycle_used_hours, "current_cycle_used_hours")
    if cycle_used > CYCLE_LIMIT_HOURS:
        raise ValueError(f"current_cycle_used_hours cannot exceed {CYCLE_LIMIT_HOURS}.")
    if FUEL_STOP_DURATION_HOURS <= 0 or not math.isfinite(FUEL_STOP_DURATION_HOURS):
        raise ValueError("FUEL_STOP_DURATION_HOURS must be a positive finite number.")
    return _TimelineBuilder(legs, cycle_used).run()

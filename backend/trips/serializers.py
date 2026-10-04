import math

from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(trim_whitespace=True, allow_blank=False)
    pickup_location = serializers.CharField(trim_whitespace=True, allow_blank=False)
    dropoff_location = serializers.CharField(trim_whitespace=True, allow_blank=False)


class TripPlanRequestSerializer(RouteRequestSerializer):
    current_cycle_used = serializers.FloatField(min_value=0, max_value=70)

    def validate_current_cycle_used(self, value):
        if not math.isfinite(value):
            raise serializers.ValidationError("A finite number between 0 and 70 is required.")
        return value

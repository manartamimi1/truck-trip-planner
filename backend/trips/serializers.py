from rest_framework import serializers


class RouteRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(trim_whitespace=True, allow_blank=False)
    pickup_location = serializers.CharField(trim_whitespace=True, allow_blank=False)
    dropoff_location = serializers.CharField(trim_whitespace=True, allow_blank=False)

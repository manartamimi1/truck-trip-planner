from django.urls import path

from .views import health, route_trip

urlpatterns = [
    path("health/", health, name="health"),
    path("trips/route/", route_trip, name="trip-route"),
]

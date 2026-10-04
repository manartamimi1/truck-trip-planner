from django.urls import path

from .views import health, plan_trip, route_trip

urlpatterns = [
    path("health/", health, name="health"),
    path("trips/route/", route_trip, name="trip-route"),
    path("trips/plan/", plan_trip, name="trip-plan"),
]

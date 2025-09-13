from django.urls import path
from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cards/", views.cards_dashboard, name="cards"),
    path("deals/", views.perks_dashboard, name="deals"),
    path("goals/", views.spending_dashboard, name="goals"),
]

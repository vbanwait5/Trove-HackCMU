from django.urls import path
from . import views


urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("cards/", views.cards_view, name="cards"),
    path("deals/", views.deals_view, name="deals"),
    path("goals/", views.spending_dashboard, name="goals"),
    path("subscriptions/", views.subscriptions_view, name="subscriptions"),

]

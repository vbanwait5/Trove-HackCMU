from django.urls import path
from . import views


urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("cards/", views.cards_dashboard, name="cards"),
    path("deals/", views.perks_dashboard, name="deals"),
    path("goals/", views.spending_dashboard, name="goals"),
    path('cards/delete/<int:card_id>/', views.delete_card, name='delete_card'),
    path("cards/add/", views.add_card, name="add_card"),
]

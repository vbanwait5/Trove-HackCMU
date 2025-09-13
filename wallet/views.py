from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .models import Transaction, Card, Deal, Goal, Subscription


@login_required
def dashboard(request):
    transactions = Transaction.objects.filter(user=request.user).order_by("-date")[:5]
    goals = Goal.objects.filter(user=request.user)
    cards = Card.objects.filter(user=request.user)
    return render(request, "wallet/dashboard.html", {
        "transactions": transactions,
        "goals": goals,
        "cards": cards,
    })


@login_required
def cards_view(request):
    cards = Card.objects.filter(user=request.user)
    return render(request, "wallet/cards.html", {"cards": cards})


@login_required
def deals_view(request):
    deals = Deal.objects.filter(card__user=request.user).order_by("expiry_date")
    return render(request, "wallet/deals.html", {"deals": deals})


@login_required
def goals_view(request):
    goals = Goal.objects.filter(user=request.user)
    return render(request, "wallet/goals.html", {"goals": goals})


@login_required
def subscriptions_view(request):
    subs = Subscription.objects.filter(user=request.user)
    return render(request, "wallet/subscriptions.html", {"subscriptions": subs})

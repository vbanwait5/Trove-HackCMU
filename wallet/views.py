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


from django.shortcuts import render
from django.db import connection  # uses your default DB (db.sqlite3)

def spending_dashboard(request):
    # Pull the latest 100 transactions and flatten categories (if present)
    with connection.cursor() as cur:
        cur.execute("""
            SELECT
                t.transaction_id,
                COALESCE(t.merchant_name, t.name, 'Unknown') AS merchant,
                COALESCE(
                    (SELECT GROUP_CONCAT(c.category, ' / ')
                     FROM transaction_categories c
                     WHERE c.transaction_id = t.transaction_id),
                    ''
                ) AS category,
                t.date AS date,
                t.amount AS amount
            FROM transactions t
            ORDER BY date DESC
            LIMIT 100;
        """)
        cols = [c[0] for c in cur.description]
        rows = cur.fetchall()
        transactions = [dict(zip(cols, r)) for r in rows]

    # If you already have goals in your DB, load them here; otherwise just pass an empty list.
    goals = []

    # Pick a budget number to drive the progress bar
    budget = 1200

    return render(
        request,
        "wallet/goals.html",  # your template from the message
        {"transactions": transactions, "goals": goals, "budget": budget},
    )

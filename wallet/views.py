from django.db.models import Sum
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


def deals_view(request):
    deals = Deal.objects.filter(card__user=request.user).order_by("expiry_date")
    return render(request, "wallet/deals.html", {"deals": deals})

@login_required
def goals_view(request):
    goals = Goal.objects.filter(user=request.user)
    transactions = Transaction.objects.filter(user=request.user).order_by("-date")[:50]

    # Budget = sum of all limits (or fallback to 1000 if no goals)
    budget = goals.aggregate(total=Sum("limit_amount"))["total"] or 1000

    # Total spent (all transactions for this user)
    total_spent = transactions.aggregate(total=Sum("amount"))["total"] or 0
    tx_count = transactions.count()
    avg_per_tx = (total_spent / tx_count) if tx_count > 0 else 0
    remaining = max(0, budget - total_spent)

    # Category totals for pie chart
    spending_by_category = (
        Transaction.objects.filter(user=request.user)
        .values("category")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    categories = [item["category"] for item in spending_by_category]
    totals = [float(item["total"]) for item in spending_by_category]

    return render(request, "wallet/goals.html", {
        "goals": goals,
        "transactions": transactions,
        "budget": budget,
        "total_spent": total_spent,
        "remaining": remaining,
        "tx_count": tx_count,
        "avg_per_tx": avg_per_tx,
        "categories": categories,
        "totals": totals,
    })

@login_required
def subscriptions_view(request):
    subs = Subscription.objects.filter(user=request.user)
    return render(request, "wallet/subscriptions.html", {"subscriptions": subs})


from django.shortcuts import render, redirect
from django.db import connection

def goals_view(request):
    if request.method == "POST":
        category = request.POST.get("category")
        limit_amount = request.POST.get("limit_amount")
        period_start = request.POST.get("period_start")
        period_end = request.POST.get("period_end")

        Goal.objects.create(
            user=request.user,
            category=category,
            limit_amount=limit_amount,
            current_spend=0,  # can update later based on transactions
            period_start=period_start,
            period_end=period_end,
        )

        return redirect("goals")  # refresh page after save

    # Query transactions (your existing SQL)
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

    goals = Goal.objects.filter(user=request.user)  # pull real goals

    budget = 1200

    return render(
        request,
        "wallet/goals.html",
        {"transactions": transactions, "goals": goals, "budget": budget},
    )

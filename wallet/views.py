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
def subscriptions_view(request):
    subs = Subscription.objects.filter(user=request.user)
    return render(request, "wallet/subscriptions.html", {"subscriptions": subs})

# wallet/views.py
from django.shortcuts import render, redirect
from django.db import connection

def spending_dashboard(request):
    if request.method == "POST":
        # Delete goal if delete form submitted
        delete_goal_id = request.POST.get("delete_goal_id")
        if delete_goal_id:
            with connection.cursor() as cur:
                cur.execute(f"DELETE FROM wallet_goal WHERE id = {delete_goal_id} AND user_id = 1;")
            return redirect("goals")

        # Otherwise: add new goal
        category = request.POST.get("category")
        limit_amount = request.POST.get("limit_amount")
        period_start = request.POST.get("period_start")
        period_end = request.POST.get("period_end")

        with connection.cursor() as cur:
            cur.execute(f"""
                INSERT INTO wallet_goal (category, limit_amount, current_spend, period_start, period_end, user_id)
                VALUES ('{category}', {limit_amount}, 0, '{period_start}', '{period_end}', 1);
            """)

        return redirect("goals")

    # --- Transactions (unchanged, the one that worked) ---
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

    # --- Goals ---
    with connection.cursor() as cur:
        cur.execute("""
            SELECT id, category, limit_amount, period_start, period_end
            FROM wallet_goal
            WHERE user_id = 1
            ORDER BY period_start DESC;
        """)
        cols = [c[0] for c in cur.description]
        raw_goals = [dict(zip(cols, r)) for r in cur.fetchall()]

    goals = []
    for g in raw_goals:
        with connection.cursor() as cur:
            cur.execute(f"""
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions t
                JOIN transaction_categories c
                  ON c.transaction_id = t.transaction_id
                WHERE c.category LIKE '%{g["category"]}%'
                  AND t.date BETWEEN '{g["period_start"]}' AND '{g["period_end"]}';
            """)
            current_spend = float(cur.fetchone()[0] or 0)

        pct = (current_spend / float(g["limit_amount"])) * 100 if g["limit_amount"] else 0
        if pct >= 75:
            color = "#ef4444"  # red
        elif pct >= 50:
            color = "#f59e0b"  # orange
        else:
            color = "#22c55e"  # green

        goals.append({
            **g,
            "current_spend": current_spend,
            "pct": pct,
            "color": color,
        })

    # --- Budget ---
    budget = sum(float(g["limit_amount"]) for g in goals) if goals else 1200

    return render(
        request,
        "wallet/goals.html",
        {"transactions": transactions, "goals": goals, "budget": budget},
    )


@login_required
def perks_dashboard(request):
    with connection.cursor() as cur:
        cur.executescript("PRAGMA foreign_keys = ON;")

    cards = {}
    with connection.cursor() as cur:
        cur.execute("""
          SELECT id, card_name, issuer, COALESCE(annual_fee, 0), type, COALESCE(base_reward_rate, 0)
          FROM cards
          ORDER BY issuer, card_name
        """)
        for cid, name, issuer, fee, ctype, base_rate in cur.fetchall():
            cards[cid] = {
                "id": cid,
                "card_name": name or "",
                "issuer": issuer or "",
                "annual_fee": float(fee or 0),
                "type": ctype or "",
                "base_reward_rate": float(base_rate or 0),
                "bonus_categories": [],
                "perks": [],
                "welcome_bonus": None,
                "current_period": None,
            }

    if not cards:
        return render(request, "wallet/deals.html", {"cards": [], "issuers": []})

    valid_ids = set(cards.keys())

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, idx, category_name, reward_rate, cap, note
          FROM bonus_categories
          ORDER BY card_id, idx
        """)
        for card_id, idx, cat_name, rate, cap, note in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["bonus_categories"].append({
                    "category_name": cat_name or "",
                    "reward_rate": float(rate or 0),
                    "cap": None if cap is None else float(cap),
                    "note": note or "",
                })

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, idx, perk_name, description, frequency
          FROM perks
          ORDER BY card_id, idx
        """)
        for card_id, idx, perk_name, desc, freq in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["perks"].append({
                    "perk_name": perk_name or "",
                    "description": desc or "",
                    "frequency": freq or "",
                })

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, points, cash_back, points_or_cash, spend_requirement, time_frame_months
          FROM welcome_bonuses
        """)
        for card_id, points, cash_back, poc, spend_req, tf_months in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["welcome_bonus"] = {
                    "points": None if points is None else int(points),
                    "cash_back": None if cash_back is None else float(cash_back),
                    "points_or_cash": None if poc is None else float(poc),
                    "spend_requirement": None if spend_req is None else float(spend_req),
                    "time_frame_months": None if tf_months is None else int(tf_months),
                }

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, start_date, end_date
          FROM card_current_period
        """)
        for card_id, start_date, end_date in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["current_period"] = {
                    "start_date": start_date,
                    "end_date": end_date,
                }

    issuers = sorted({(c["issuer"] or "").strip() for c in cards.values() if c["issuer"]})
    return render(request, "wallet/deals.html", {
        "cards": list(cards.values()),
        "issuers": issuers,
    })
    
@login_required
def cards_dashboard(request):
    with connection.cursor() as cur:
        cur.executescript("PRAGMA foreign_keys = ON;")

    cards = {}
    with connection.cursor() as cur:
        cur.execute("""
          SELECT id, card_name, issuer, COALESCE(annual_fee, 0), type, COALESCE(base_reward_rate, 0)
          FROM cards
          ORDER BY issuer, card_name
        """)
        for cid, name, issuer, fee, ctype, base_rate in cur.fetchall():
            cards[cid] = {
                "id": cid,
                "card_name": name or "",
                "issuer": issuer or "",
                "annual_fee": float(fee or 0),
                "type": ctype or "",
                "base_reward_rate": float(base_rate or 0),
                "bonus_categories": [],
                "perks": [],
                "welcome_bonus": None,
                "current_period": None,
            }

    valid_ids = set(cards.keys())

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, idx, category_name, reward_rate, cap, note
          FROM bonus_categories
          ORDER BY card_id, idx
        """)
        for card_id, idx, cat_name, rate, cap, note in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["bonus_categories"].append({
                    "category_name": cat_name or "",
                    "reward_rate": float(rate or 0),
                    "cap": None if cap is None else float(cap),
                    "note": note or "",
                })

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, idx, perk_name, description, frequency
          FROM perks
          ORDER BY card_id, idx
        """)
        for card_id, idx, perk_name, desc, freq in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["perks"].append({
                    "perk_name": perk_name or "",
                    "description": desc or "",
                    "frequency": freq or "",
                })

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, points, cash_back, points_or_cash, spend_requirement, time_frame_months
          FROM welcome_bonuses
        """)
        for card_id, points, cash_back, poc, spend_req, tf_months in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["welcome_bonus"] = {
                    "points": None if points is None else int(points),
                    "cash_back": None if cash_back is None else float(cash_back),
                    "points_or_cash": None if poc is None else float(poc),
                    "spend_requirement": None if spend_req is None else float(spend_req),
                    "time_frame_months": None if tf_months is None else int(tf_months),
                }

    with connection.cursor() as cur:
        cur.execute("""
          SELECT card_id, start_date, end_date
          FROM card_current_period
        """)
        for card_id, start_date, end_date in cur.fetchall():
            if card_id in valid_ids:
                cards[card_id]["current_period"] = {
                    "start_date": start_date,
                    "end_date": end_date,
                }

    # Calculate total annual fee
    total_fee = sum(card["annual_fee"] for card in cards.values())

    return render(request, "wallet/cards.html", {
        "cards": list(cards.values()),
        "total_fee": total_fee
    })
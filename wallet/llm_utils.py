import os
import openai
from wallet.models import Transaction
from django.db.models import Sum
from datetime import date, timedelta

openai.api_key = os.getenv("OPENAI_API_KEY")

def generate_spending_report(user, query="Give me a summary of my spending."):
    # 1. Pull data from DB
    transactions = Transaction.objects.filter(user=user).order_by("-date")[:100]
    
    # Convert to simple JSON-like structure
    txn_list = [
        {
            "date": str(t.date),
            "merchant": t.merchant,
            "category": t.category,
            "amount": float(t.amount),
            "card": t.card.name if t.card else None,
        }
        for t in transactions
    ]
    
    # 2. Build prompt
    system_prompt = """You are Trove, an AI financial analyst.
You analyze spending, answer financial queries, create budget plans,
and help the user optimize credit card usage."""
    
    user_prompt = f"""
Here are the user’s last {len(txn_list)} transactions:
{txn_list}

The user’s request: {query}
Please provide a clear, actionable response.
"""
    
    # 3. Call OpenAI
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=600,
    )
    
    return response.choices[0].message["content"]

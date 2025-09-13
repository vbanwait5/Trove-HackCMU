from django.db import models
from django.contrib.auth.models import User


class Card(models.Model):
    CARD_TYPES = [
        ("credit", "Credit"),
        ("debit", "Debit"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cards")
    name = models.CharField(max_length=100)  # e.g. "Amex Gold"
    issuer = models.CharField(max_length=100)  # e.g. "American Express"
    card_type = models.CharField(max_length=10, choices=CARD_TYPES, default="credit")
    annual_fee = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    base_reward_rate = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)  # e.g. 1x

    def __str__(self):
        return f"{self.name} ({self.issuer})"


class Deal(models.Model):
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name="deals")
    description = models.TextField()
    category = models.CharField(max_length=100, null=True, blank=True)  # e.g. Dining, Travel
    reward_rate = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    expiry_date = models.DateField(null=True, blank=True)
    activation_required = models.BooleanField(default=False)

    def __str__(self):
        return f"Deal for {self.card.name}: {self.description[:50]}"


class Transaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="transactions")
    card = models.ForeignKey(Card, on_delete=models.SET_NULL, null=True, blank=True)
    merchant = models.CharField(max_length=200)
    category = models.CharField(max_length=100)  # e.g. "Dining", "Groceries"
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.merchant} - ${self.amount} on {self.date}"


class Goal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="goals")
    category = models.CharField(max_length=100)  # e.g. Dining, Travel
    limit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    current_spend = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    period_start = models.DateField()
    period_end = models.DateField()

    def __str__(self):
        return f"{self.user.username} - {self.category} goal"


class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    merchant = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=50, default="monthly")  # monthly, yearly
    next_payment_date = models.DateField()

    def __str__(self):
        return f"{self.merchant} - {self.amount}/{self.billing_cycle}"

class Account(models.Model):
    # These fields must match the column names in your 'accounts' table.
    official_name = models.CharField(max_length=255)
    subtype = models.CharField(max_length=100)
    # Add any other columns you might want to access from the table.

    class Meta:
        managed = False  # Tells Django not to manage this table's schema (e.g., migrations)
        db_table = 'accounts' # The exact name of your existing table in the database

    def __str__(self):
        return self.official_name
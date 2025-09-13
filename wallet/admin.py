from django.contrib import admin
from .models import Card, Deal, Transaction, Goal, Subscription

admin.site.register(Card)
admin.site.register(Deal)
admin.site.register(Transaction)
admin.site.register(Goal)
admin.site.register(Subscription)

import json
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from wallet.models import Card, Transaction


class Command(BaseCommand):
    help = "Import dummy Plaid JSON transactions into the database"

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to Plaid JSON file")
        parser.add_argument(
            "--user", type=str, default=None,
            help="Username to assign imported cards/transactions to"
        )

    def handle(self, *args, **options):
        file_path = options["json_file"]
        username = options["user"]

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Error reading file: {e}"))
            return

        if username:
            user = User.objects.get(username=username)
        else:
            # default to first superuser if not provided
            user = User.objects.filter(is_superuser=True).first()

        if not user:
            self.stderr.write(self.style.ERROR("No valid user found."))
            return

        account_map = {}

        # Import accounts as Cards
        for acc in data.get("accounts", []):
            card, _ = Card.objects.get_or_create(
                user=user,
                name=acc["name"],
                issuer=acc.get("official_name", "Unknown Issuer"),
                defaults={
                    "card_type": "credit",
                    "annual_fee": 0,
                    "base_reward_rate": 1.0,
                },
            )
            account_map[acc["account_id"]] = card

        # Import transactions
        for txn in data.get("transactions", []):
            card = account_map.get(txn["account_id"])
            Transaction.objects.create(
                user=user,
                card=card,
                merchant=txn["merchant_name"],
                category=", ".join(txn.get("category", [])),
                amount=txn["amount"],
                date=txn["date"],
            )

        self.stdout.write(self.style.SUCCESS("Plaid JSON imported successfully."))

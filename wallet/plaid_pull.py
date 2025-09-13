# wallet/plaid_pull.py
import os, json, importlib.util
from decimal import Decimal
from pathlib import Path

# Plaid SDK imports (NO Environment enum needed)
try:
    from plaid import Configuration, ApiClient
except ImportError:
    from plaid.configuration import Configuration
    from plaid.api_client import ApiClient

from plaid.api import plaid_api
from plaid.model.products import Products
from plaid.model.item_public_token_exchange_request import ItemPublicTokenExchangeRequest
from plaid.model.accounts_get_request import AccountsGetRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest
from plaid.model.sandbox_public_token_create_request import SandboxPublicTokenCreateRequest

# --- add near the top of plaid_pull.py, below imports ---
import sqlite3

def _s(v):
    """Make Plaid enums/objects JSON-serializable (unwrap to str)."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return getattr(v, "value", str(v))

def _db_counts(db_path: Path):
    """Quick debug counts to confirm we wrote to the DB we think we did."""
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        counts = {}
        for table in ("accounts", "transactions", "transaction_categories", "items", "meta"):
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cur.fetchone():
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            else:
                counts[table] = "MISSING"
        conn.close()
        return counts
    except Exception as e:
        return {"error": str(e)}


def _plaid_host() -> str:
    env = (os.getenv("PLAID_ENV") or "sandbox").lower()
    return {
        "sandbox":     "https://sandbox.plaid.com",
        "development": "https://development.plaid.com",
        "production":  "https://production.plaid.com",
    }.get(env, "https://sandbox.plaid.com")


def _plaid_client() -> plaid_api.PlaidApi:
    cfg = Configuration(
        host=_plaid_host(),  # <- use URL string, not Environment enum
        api_key={
            "clientId": os.getenv("PLAID_CLIENT_ID", ""),
            "secret":   os.getenv("PLAID_SECRET", ""),
        },
    )
    return plaid_api.PlaidApi(ApiClient(cfg))


def _sandbox_access_token() -> str:
    """
    Create a Sandbox public_token (no UI) and exchange it.
    Institution: First Platypus Bank (ins_109508).
    """
    client = _plaid_client()
    pub = client.sandbox_public_token_create(
        SandboxPublicTokenCreateRequest(
            institution_id="ins_109508",
            initial_products=[Products("transactions")],
        )
    )
    exch = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=pub.public_token)
    )
    return exch.access_token


def _transactions_sync(access_token: str):
    """Fetch ALL transactions using /transactions/sync without passing cursor=None."""
    client = _plaid_client()
    added, modified, removed, req_id = [], [], [], None
    cursor, has_more = None, True

    while has_more:
        # IMPORTANT: omit cursor on the very first request
        if cursor:
            req = TransactionsSyncRequest(access_token=access_token, cursor=cursor)
        else:
            req = TransactionsSyncRequest(access_token=access_token)

        resp = client.transactions_sync(req)

        added.extend(resp.added)
        modified.extend(resp.modified)
        removed.extend(resp.removed)

        cursor = resp.next_cursor
        has_more = resp.has_more
        req_id = getattr(resp, "request_id", None)

    return added, modified, removed, req_id


def _accounts(access_token: str):
    client = _plaid_client()
    return client.accounts_get(AccountsGetRequest(access_token=access_token)).accounts


def _make_loader_dict(access_token: str) -> dict:
    added, modified, removed, req_id = _transactions_sync(access_token)
    accts = _accounts(access_token)

    accounts_json = [{
        "account_id": a.account_id,
        "mask": _s(getattr(a, "mask", None)),
        "name": _s(getattr(a, "name", None)),
        "official_name": _s(getattr(a, "official_name", None)),
        "subtype": _s(getattr(a, "subtype", None)),
        "type": _s(getattr(a, "type", None)),
    } for a in accts]

    tx_json = []
    for t in (added + modified):
        tx_json.append({
            "transaction_id": t.transaction_id,
            "account_id": t.account_id,
            "amount": float(Decimal(str(t.amount))),
            "date": str(t.date),
            "name": _s(getattr(t, "name", "")),
            "merchant_name": _s(getattr(t, "merchant_name", "")),
            "payment_channel": _s(getattr(t, "payment_channel", "")),
            "category": [_s(c) for c in (getattr(t, "category", []) or [])],
        })

    return {
        "accounts": accounts_json,
        "transactions": tx_json,
        "item": {"item_id": "", "institution_id": "", "webhook": ""},
        "request_id": req_id or "",
        "total_transactions": len(tx_json),
    }

def _import_loader(loader_path: Path):
    spec = importlib.util.spec_from_file_location("loader_mod", loader_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sync_plaid_to_sqlite(json_path: Path, db_path: Path, loader_path: Path):
    """
    1) Pull Sandbox data
    2) Write JSON in your loader's shape
    3) Call your loader (load(json_path, db_path))
    4) Return counts for quick verification
    """
    access_token = _sandbox_access_token()
    data = _make_loader_dict(access_token)

    json_path = json_path.resolve()
    db_path = db_path.resolve()
    loader_path = loader_path.resolve()

    json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    loader = _import_loader(loader_path)
    # Your loader reads the JSON file and writes to SQLite
    loader.load(str(json_path), str(db_path))

    counts = _db_counts(db_path)
    print(f"[Plaid→Loader] JSON: {json_path}")
    print(f"[Plaid→Loader] DB:   {db_path}")
    print(f"[Plaid→Loader] Counts after load: {counts}")
    return counts

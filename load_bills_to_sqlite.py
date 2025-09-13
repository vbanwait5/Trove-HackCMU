
import json, sqlite3, sys, os

def ensure_schema(cur):
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS accounts (
      account_id     TEXT PRIMARY KEY,
      mask           TEXT,
      name           TEXT,
      official_name  TEXT,
      subtype        TEXT,
      type           TEXT
    );

    CREATE TABLE IF NOT EXISTS transactions (
      transaction_id   TEXT PRIMARY KEY,
      account_id       TEXT NOT NULL,
      amount           REAL NOT NULL,
      date             TEXT NOT NULL,
      name             TEXT,
      merchant_name    TEXT,
      payment_channel  TEXT,
      FOREIGN KEY (account_id) REFERENCES accounts(account_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS transaction_categories (
      transaction_id TEXT NOT NULL,
      idx            INTEGER NOT NULL,
      category       TEXT NOT NULL,
      PRIMARY KEY (transaction_id, idx),
      FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS items (
      item_id         TEXT PRIMARY KEY,
      institution_id  TEXT,
      webhook         TEXT
    );

    CREATE TABLE IF NOT EXISTS meta (
      request_id         TEXT,
      total_transactions INTEGER
    );

    CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
    CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
    """)

def load(json_path, db_path):
    if not os.path.exists(json_path):
        raise SystemExit(f"JSON not found: {json_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ensure_schema(cur)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Accounts
    for a in data.get("accounts", []):
        cur.execute("""
            INSERT OR REPLACE INTO accounts (account_id, mask, name, official_name, subtype, type)
            VALUES (:account_id, :mask, :name, :official_name, :subtype, :type)
        """, a)

    # Transactions and categories
    for t in data.get("transactions", []):
        cur.execute("""
            INSERT OR REPLACE INTO transactions (transaction_id, account_id, amount, date, name, merchant_name, payment_channel)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            t.get("transaction_id"),
            t.get("account_id"),
            float(t.get("amount", 0)),
            t.get("date"),
            t.get("name"),
            t.get("merchant_name"),
            t.get("payment_channel"),
        ))
        # Replace category entries for this transaction
        cur.execute("DELETE FROM transaction_categories WHERE transaction_id = ?", (t.get("transaction_id"),))
        for i, cat in enumerate(t.get("category", [])):
            cur.execute("""
                INSERT INTO transaction_categories (transaction_id, idx, category)
                VALUES (?, ?, ?)
            """, (t["transaction_id"], i, cat))

    # Item
    item = data.get("item", {})
    if item and item.get("item_id"):
        cur.execute("""
            INSERT OR REPLACE INTO items (item_id, institution_id, webhook)
            VALUES (:item_id, :institution_id, :webhook)
        """, item)

    # Meta (truncate and insert single row)
    cur.execute("DELETE FROM meta")
    cur.execute("INSERT INTO meta (request_id, total_transactions) VALUES (?, ?)",
                (data.get("request_id"), data.get("total_transactions")))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Usage: python load_bills_to_sqlite.py /path/to/bills.json /path/to/db.sqlite3
    # Defaults to: bills.json (current dir) and db.sqlite3 (current dir)
    json_path = sys.argv[1] if len(sys.argv) > 1 else "bills.json"
    db_path = sys.argv[2] if len(sys.argv) > 2 else "db.sqlite3"
    load(json_path, db_path)
    print(f"Loaded {json_path} into {db_path}")

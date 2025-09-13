# load_perks_to_sqlite.py
import json, sqlite3, sys, os
from typing import Any, Dict, List

def ensure_schema(cur: sqlite3.Cursor):
    cur.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS cards (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      card_name        TEXT NOT NULL,
      issuer           TEXT,
      annual_fee       REAL,
      type             TEXT,
      base_reward_rate REAL,
      UNIQUE(card_name, issuer)
    );

    CREATE TABLE IF NOT EXISTS bonus_categories (
      card_id       INTEGER NOT NULL,
      idx           INTEGER NOT NULL,
      category_name TEXT NOT NULL,
      reward_rate   REAL,
      cap           REAL,
      note          TEXT,
      PRIMARY KEY (card_id, idx),
      FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS perks (
      card_id     INTEGER NOT NULL,
      idx         INTEGER NOT NULL,
      perk_name   TEXT NOT NULL,
      description TEXT,
      frequency   TEXT,
      PRIMARY KEY (card_id, idx),
      FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS welcome_bonuses (
      card_id            INTEGER PRIMARY KEY,
      points             INTEGER,
      cash_back          REAL,
      points_or_cash     REAL,
      spend_requirement  REAL,
      time_frame_months  INTEGER,
      FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS card_current_period (
      card_id    INTEGER PRIMARY KEY,
      start_date TEXT,
      end_date   TEXT,
      FOREIGN KEY (card_id) REFERENCES cards(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_cards_issuer ON cards(issuer);
    CREATE INDEX IF NOT EXISTS idx_bonus_categories_card ON bonus_categories(card_id);
    CREATE INDEX IF NOT EXISTS idx_perks_card ON perks(card_id);
    """)

def upsert_card(cur: sqlite3.Cursor, c: Dict[str, Any]) -> int:
    # Normalize
    card_name = c.get("card_name")
    issuer = c.get("issuer")
    annual_fee = c.get("annual_fee")
    ctype = c.get("type")
    base_rate = c.get("base_reward_rate")

    # SQLite UPSERT on UNIQUE(card_name, issuer)
    cur.execute("""
        INSERT INTO cards (card_name, issuer, annual_fee, type, base_reward_rate)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(card_name, issuer) DO UPDATE SET
          annual_fee=excluded.annual_fee,
          type=excluded.type,
          base_reward_rate=excluded.base_reward_rate
    """, (card_name, issuer, annual_fee, ctype, base_rate))

    cur.execute("SELECT id FROM cards WHERE card_name=? AND issuer=?", (card_name, issuer))
    row = cur.fetchone()
    return int(row[0])

def upsert_welcome_bonus(cur: sqlite3.Cursor, card_id: int, wb: Dict[str, Any] | None):
    # Normalize any shape into a single row (nullable columns for whichever apply)
    points = (wb or {}).get("points")
    cash_back = (wb or {}).get("cash_back")
    points_or_cash = (wb or {}).get("points_or_cash")
    spend_req = (wb or {}).get("spend_requirement")
    tf_months = (wb or {}).get("time_frame_months")

    cur.execute("DELETE FROM welcome_bonuses WHERE card_id = ?", (card_id,))
    cur.execute("""
        INSERT INTO welcome_bonuses (card_id, points, cash_back, points_or_cash, spend_requirement, time_frame_months)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (card_id, points, cash_back, points_or_cash, spend_req, tf_months))

def replace_bonus_categories(cur: sqlite3.Cursor, card_id: int, cats: List[Dict[str, Any]] | None):
    cur.execute("DELETE FROM bonus_categories WHERE card_id = ?", (card_id,))
    if not cats:
        return
    for i, cat in enumerate(cats):
        cur.execute("""
            INSERT INTO bonus_categories (card_id, idx, category_name, reward_rate, cap, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            card_id,
            i,
            cat.get("category_name"),
            cat.get("reward_rate"),
            cat.get("cap"),
            cat.get("note"),
        ))

def replace_perks(cur: sqlite3.Cursor, card_id: int, perks: List[Dict[str, Any]] | None):
    cur.execute("DELETE FROM perks WHERE card_id = ?", (card_id,))
    if not perks:
        return
    for i, p in enumerate(perks):
        cur.execute("""
            INSERT INTO perks (card_id, idx, perk_name, description, frequency)
            VALUES (?, ?, ?, ?, ?)
        """, (
            card_id,
            i,
            p.get("perk_name"),
            p.get("description"),
            p.get("frequency"),
        ))

def upsert_current_period(cur: sqlite3.Cursor, card_id: int, period: Dict[str, Any] | None):
    cur.execute("DELETE FROM card_current_period WHERE card_id = ?", (card_id,))
    if not period:
        return
    cur.execute("""
        INSERT INTO card_current_period (card_id, start_date, end_date)
        VALUES (?, ?, ?)
    """, (card_id, period.get("start_date"), period.get("end_date")))

def load(json_path: str, db_path: str):
    if not os.path.exists(json_path):
        raise SystemExit(f"JSON not found: {json_path}")

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    ensure_schema(cur)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # The file is an array of card objects; support dict->list just in case.
    items = data if isinstance(data, list) else [data]

    for card in items:
        card_id = upsert_card(cur, card)
        upsert_welcome_bonus(cur, card_id, card.get("welcome_bonus"))
        replace_bonus_categories(cur, card_id, card.get("bonus_categories"))
        replace_perks(cur, card_id, card.get("perks"))
        upsert_current_period(cur, card_id, card.get("current_period"))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Usage:
    #   python load_perks_to_sqlite.py /path/to/perk_data.json /path/to/db.sqlite3
    # Defaults to files in current directory.
    json_path = sys.argv[1] if len(sys.argv) > 1 else "perk_data.json"
    db_path = sys.argv[2] if len(sys.argv) > 2 else "db.sqlite3"
    load(json_path, db_path)
    print(f"Loaded {json_path} into {db_path}")

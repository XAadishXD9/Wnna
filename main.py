#!/usr/bin/env python3
"""
Safe promo-code generator & validator.
- Generates codes and stores them in a local SQLite DB.
- Allows listing, validating, and redeeming codes.
- Intended for *your own* app/promo system. No external Discord or third-party API calls.
"""

import sqlite3
import secrets
import string
import time
from datetime import datetime

DB_PATH = "codes.db"

# ------------ Database helpers ------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL,
            redeemed INTEGER NOT NULL DEFAULT 0,
            redeemed_at TEXT
        )
        """
    )
    conn.commit()
    return conn

# ------------ Code generation ------------
def generate_code(length=16, alphabet=None):
    if alphabet is None:
        alphabet = string.ascii_uppercase + string.digits + string.ascii_lowercase
    # use secrets for cryptographically secure random generation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def add_codes(conn, count, length=16):
    cur = conn.cursor()
    added = 0
    start = time.time()
    while added < count:
        code = generate_code(length=length)
        created_at = datetime.utcnow().isoformat() + "Z"
        try:
            cur.execute("INSERT INTO codes (code, created_at) VALUES (?, ?)", (code, created_at))
            added += 1
        except sqlite3.IntegrityError:
            # duplicate code generated — try again
            continue
    conn.commit()
    elapsed = time.time() - start
    return added, elapsed

# ------------ Listing / Checking / Redeeming ------------
def list_codes(conn, show_redeemed=False, limit=100):
    cur = conn.cursor()
    if show_redeemed:
        cur.execute("SELECT code, created_at, redeemed, redeemed_at FROM codes ORDER BY id DESC LIMIT ?", (limit,))
    else:
        cur.execute("SELECT code, created_at, redeemed, redeemed_at FROM codes WHERE redeemed=0 ORDER BY id DESC LIMIT ?", (limit,))
    return cur.fetchall()

def check_code(conn, code):
    cur = conn.cursor()
    cur.execute("SELECT id, code, redeemed, redeemed_at FROM codes WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        return {"exists": False}
    return {"exists": True, "redeemed": bool(row[2]), "redeemed_at": row[3]}

def redeem_code(conn, code):
    cur = conn.cursor()
    info = check_code(conn, code)
    if not info["exists"]:
        return {"ok": False, "reason": "not_found"}
    if info["redeemed"]:
        return {"ok": False, "reason": "already_redeemed", "redeemed_at": info["redeemed_at"]}
    redeemed_at = datetime.utcnow().isoformat() + "Z"
    cur.execute("UPDATE codes SET redeemed = 1, redeemed_at = ? WHERE code = ?", (redeemed_at, code))
    conn.commit()
    return {"ok": True, "redeemed_at": redeemed_at}

# ------------ CLI ------------
def main_menu():
    conn = init_db()
    menu = """
    SAFE Code Manager
    1) Generate codes
    2) List codes (unredeemed)
    3) List codes (all)
    4) Check code
    5) Redeem code
    6) Quit
    """
    while True:
        print(menu)
        choice = input("Choose an option (1-6): ").strip()
        if choice == '1':
            try:
                n = int(input("How many codes to generate? ").strip())
                length = int(input("Code length (e.g. 16): ").strip())
            except ValueError:
                print("Invalid number. Try again.")
                continue
            added, elapsed = add_codes(conn, n, length=length)
            print(f"Added {added} codes in {elapsed:.2f} seconds. Stored in {DB_PATH}.")
        elif choice == '2':
            rows = list_codes(conn, show_redeemed=False, limit=500)
            if not rows:
                print("No unredeemed codes found.")
            else:
                print(f"Unredeemed codes (showing {len(rows)}):")
                for r in rows:
                    print(f" {r[0]}  created: {r[1]}")
        elif choice == '3':
            rows = list_codes(conn, show_redeemed=True, limit=500)
            if not rows:
                print("No codes found.")
            else:
                print(f"All codes (showing {len(rows)}):")
                for r in rows:
                    status = "Redeemed" if r[2] else "Unredeemed"
                    ra = r[3] if r[3] else "-"
                    print(f" {r[0]}  {status}  created: {r[1]}  redeemed_at: {ra}")
        elif choice == '4':
            code = input("Enter code to check: ").strip()
            info = check_code(conn, code)
            if not info["exists"]:
                print("Code not found.")
            else:
                if info["redeemed"]:
                    print(f"Code exists and was already redeemed at {info['redeemed_at']}.")
                else:
                    print("Code exists and is unredeemed.")
        elif choice == '5':
            code = input("Enter code to redeem: ").strip()
            result = redeem_code(conn, code)
            if result["ok"]:
                print(f"Code redeemed successfully at {result['redeemed_at']}.")
            else:
                if result["reason"] == "not_found":
                    print("Code not found.")
                elif result["reason"] == "already_redeemed":
                    print(f"Code was already redeemed at {result.get('redeemed_at')}.")
                else:
                    print("Could not redeem code:", result)
        elif choice == '6':
            print("Bye.")
            conn.close()
            break
        else:
            print("Invalid choice. Try again.")

if __name__ == "__main__":
    main_menu()

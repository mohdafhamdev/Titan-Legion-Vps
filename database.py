import sqlite3
import json
import os

DB_FILE = "users.db"


def _get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            uid TEXT PRIMARY KEY,
            name TEXT,
            points INTEGER,
            spins INTEGER,
            last_spin REAL
        )
        """
    )
    return conn


def load_users() -> dict:
    """Returns all users as a dict, same shape as the old JSON version:
    { "12345": {"name": ..., "points": ..., "spins": ..., "last_spin": ...}, ... }
    """
    conn = _get_connection()
    cursor = conn.execute("SELECT uid, name, points, spins, last_spin FROM users")

    users = {}
    for uid, name, points, spins, last_spin in cursor.fetchall():
        users[uid] = {
            "name": name,
            "points": points,
            "spins": spins,
            "last_spin": last_spin,
        }

    conn.close()
    return users


def save_users(users: dict):
    """Overwrites the full users table with the given dict.
    Called the same way as before: save_users(users)
    """
    conn = _get_connection()

    # Clear and rewrite (matches old JSON "overwrite everything" behavior,
    # including wiping all data when save_users({}) is called for /resetdata)
    conn.execute("DELETE FROM users")

    for uid, data in users.items():
        conn.execute(
            "INSERT INTO users (uid, name, points, spins, last_spin) VALUES (?, ?, ?, ?, ?)",
            (
                uid,
                data.get("name", "Unknown"),
                data.get("points", 0),
                data.get("spins", 0),
                data.get("last_spin", 0),
            ),
        )

    conn.commit()
    conn.close()


def migrate_from_json(json_path: str = "users.json"):
    """One-time helper: run this once if you have an existing users.json
    and want to import its data into the new SQLite database.
    """
    if not os.path.exists(json_path):
        print(f"No {json_path} found — nothing to migrate.")
        return

    with open(json_path, "r") as f:
        old_users = json.load(f)

    save_users(old_users)
    print(f"Migrated {len(old_users)} user(s) from {json_path} into {DB_FILE}.")


if __name__ == "__main__":
    # Run this file directly (python3 database.py) to migrate old JSON data, if any.
    migrate_from_json()

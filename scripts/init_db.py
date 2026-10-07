"""
Idempotent migration runner.

Usage:
    python scripts/init_db.py
"""

import os
import sys

# Ensure the project root is on sys.path so `import app` works
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db.session import engine

MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "app", "db", "migrations",
)


def run_migrations() -> None:
    migration_files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR) if f.endswith(".sql")
    )
    if not migration_files:
        print("No migration files found.")
        return

    print(f"Running {len(migration_files)} migrations against: {engine.url}")
    with engine.begin() as conn:
        for filename in migration_files:
            path = os.path.join(MIGRATIONS_DIR, filename)
            with open(path, "r", encoding="utf-8") as fh:
                sql = fh.read()
            conn.execute(text(sql))
            print(f"  [OK] {filename}")

    print("All migrations completed successfully.")


if __name__ == "__main__":
    run_migrations()

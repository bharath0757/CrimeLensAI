"""Wait for the one-shot database bootstrap before starting the ledger API."""

import os
import time

import psycopg2
from sqlalchemy.engine import make_url

EXPECTED_MIGRATIONS = {
    "001_audit_outbox",
    "002_structured_ingestion",
    "003_runtime_roles",
}


def psycopg_database_url(database_url: str) -> str:
    """Normalize SQLAlchemy PostgreSQL URLs for psycopg2.connect()."""
    parsed = make_url(database_url)
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("Database URL must use PostgreSQL")
    return parsed.set(drivername="postgresql").render_as_string(hide_password=False)


def schema_ready(database_url: str) -> bool:
    try:
        connect_url = psycopg_database_url(database_url)
        with psycopg2.connect(connect_url, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.schema_migrations')")
            if cursor.fetchone()[0] is None:
                return False
            cursor.execute("SELECT version FROM public.schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='crimelens_ledger'")
            ledger_role_exists = cursor.fetchone() is not None
        return EXPECTED_MIGRATIONS.issubset(applied) and ledger_role_exists
    except (psycopg2.Error, ValueError):
        return False


def main() -> None:
    database_url = (
        os.getenv("MIGRATION_DATABASE_URL", "").strip()
        or os.getenv("LEDGER_DATABASE_URL", "").strip()
    )
    if not database_url:
        raise RuntimeError("MIGRATION_DATABASE_URL or LEDGER_DATABASE_URL is required")
    timeout_seconds = int(os.getenv("SCHEMA_WAIT_TIMEOUT_SECONDS", "300"))
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if schema_ready(database_url):
            print("Database schema is ready; starting audit ledger", flush=True)
            return
        time.sleep(2)
    raise RuntimeError(f"Database schema was not ready after {timeout_seconds} seconds")


if __name__ == "__main__":
    main()

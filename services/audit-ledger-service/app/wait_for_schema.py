"""Wait for the one-shot database bootstrap before starting the ledger API."""

import os
import time

import psycopg2

EXPECTED_MIGRATIONS = {
    "001_audit_outbox",
    "002_structured_ingestion",
    "003_runtime_roles",
}


def schema_ready(database_url: str) -> bool:
    try:
        with psycopg2.connect(database_url, connect_timeout=5) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.schema_migrations')")
            if cursor.fetchone()[0] is None:
                return False
            cursor.execute("SELECT version FROM public.schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname='crimelens_ledger'")
            ledger_role_exists = cursor.fetchone() is not None
        return EXPECTED_MIGRATIONS.issubset(applied) and ledger_role_exists
    except psycopg2.Error:
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

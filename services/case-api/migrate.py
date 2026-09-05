import os
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("MIGRATION_DATABASE_URL or DATABASE_URL is required")


def run_sql_file(connection, path):
    print(f"Running {path}")
    sql = path.read_text(encoding="utf-8")
    with connection.cursor() as cursor:
        cursor.execute(sql)
    connection.commit()


def main():
    connection = psycopg2.connect(DATABASE_URL)

    try:
        run_sql_file(connection, ROOT / "database" / "schema.sql")
        run_sql_file(
            connection,
            ROOT / "database" / "migrations" / "001_audit_outbox.sql",
        )
        run_sql_file(
            connection,
            ROOT / "database" / "migrations" / "002_structured_ingestion.sql",
        )
        run_sql_file(
            connection,
            ROOT / "database" / "migrations" / "003_runtime_roles.sql",
        )

        print("Database migrations completed successfully")

    finally:
        connection.close()


if __name__ == "__main__":
    main()

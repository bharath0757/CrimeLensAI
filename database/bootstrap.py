"""One-shot, concurrent-safe schema migration, administrator bootstrap and optional demo seed."""

import os
import re
import subprocess

import bcrypt
import psycopg2
from psycopg2.extensions import parse_dsn

EXPECTED_MIGRATIONS = {
    "001_audit_outbox",
    "002_structured_ingestion",
    "003_runtime_roles",
}


def required(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def validate_password(name: str) -> str:
    value = required(name)
    if len(value) < 12 or len(value.encode()) > 72:
        raise RuntimeError(f"{name} must contain 12 to 72 UTF-8 bytes")
    return value


def psql_environment(database_url: str) -> dict[str, str]:
    """Give psql the same database used by psycopg2 without exposing its URL."""
    environment = os.environ.copy()
    if not database_url:
        return environment
    parameters = parse_dsn(database_url)
    mapping = {
        "host": "PGHOST",
        "hostaddr": "PGHOSTADDR",
        "port": "PGPORT",
        "dbname": "PGDATABASE",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "sslmode": "PGSSLMODE",
        "options": "PGOPTIONS",
    }
    for source, target in mapping.items():
        if parameters.get(source):
            environment[target] = parameters[source]
    environment.setdefault("PGCONNECT_TIMEOUT", "15")
    return environment


def run_psql(path: str, database_url: str, *variables: str) -> None:
    command = ["psql", "--no-psqlrc", "--echo-errors", "--set", "ON_ERROR_STOP=1"]
    for variable in variables:
        command.extend(["--set", variable])
    command.extend(["--file", path])
    subprocess.run(command, check=True, env=psql_environment(database_url))


def verify_schema(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.schema_migrations')")
        if cursor.fetchone()[0] is None:
            raise RuntimeError("Migration failed: public.schema_migrations was not created")
        cursor.execute("SELECT version FROM public.schema_migrations")
        applied = {row[0] for row in cursor.fetchall()}
    missing = EXPECTED_MIGRATIONS - applied
    if missing:
        raise RuntimeError(f"Migration failed: missing versions {sorted(missing)}")


def configure_accounts(connection, admin_email: str, admin_password: str) -> None:
    api_password = validate_password("API_DATABASE_PASSWORD")
    ledger_password = validate_password("LEDGER_DATABASE_PASSWORD")
    for name, value in (("API_DATABASE_PASSWORD", api_password), ("LEDGER_DATABASE_PASSWORD", ledger_password)):
        if len(value) < 32 or any(character.isspace() or character == "\x00" for character in value):
            raise RuntimeError(f"{name} must contain 32 to 72 non-whitespace characters")
    with connection.cursor() as cursor:
        for role, password in (("crimelens_api", api_password), ("crimelens_ledger", ledger_password)):
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
            if cursor.fetchone():
                cursor.execute(f'ALTER ROLE "{role}" LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', (password,))
            else:
                cursor.execute(f'CREATE ROLE "{role}" LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION', (password,))
        cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cursor.execute("GRANT USAGE ON SCHEMA public TO crimelens_api,crimelens_ledger")
        cursor.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON users,cases,documents,entities,relationships,cdr_records,transactions TO crimelens_api")
        cursor.execute("GRANT SELECT,INSERT,UPDATE ON audit_outbox,ingestion_batches TO crimelens_api")
        cursor.execute("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO crimelens_api")
        cursor.execute("GRANT SELECT,INSERT ON ledger_entries TO crimelens_ledger")
        cursor.execute("GRANT SELECT,UPDATE ON ledger_head TO crimelens_ledger")
        cursor.execute("GRANT SELECT ON schema_migrations TO crimelens_api,crimelens_ledger")
        password_hash = bcrypt.hashpw(admin_password.encode(), bcrypt.gensalt()).decode()
        cursor.execute("""INSERT INTO users(id,email,password_hash,full_name,role,badge_number,agency)
            VALUES ('deployment-admin',%s,%s,'Deployment Administrator','ADMIN','DEPLOY-ADMIN','Configured deployment')
            ON CONFLICT(id) DO UPDATE SET email=EXCLUDED.email,password_hash=EXCLUDED.password_hash,
                role='ADMIN',is_active=TRUE,updated_at=NOW()""",
            (admin_email, password_hash))


def main() -> None:
    admin_email = required("BOOTSTRAP_ADMIN_EMAIL").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", admin_email):
        raise RuntimeError("BOOTSTRAP_ADMIN_EMAIL must be a valid email address")
    admin_password = validate_password("BOOTSTRAP_ADMIN_PASSWORD")
    seed = os.getenv("SEED_SYNTHETIC", "false").lower() == "true"
    if seed and os.getenv("ALLOW_DEMO_SEED", "false").lower() != "true":
        raise RuntimeError("Synthetic demo seeding also requires ALLOW_DEMO_SEED=true")
    migration_url = os.getenv("MIGRATION_DATABASE_URL", "").strip()
    connection = psycopg2.connect(migration_url)
    connection.autocommit = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(26189,42)")
            cursor.execute("SELECT current_database()")
            database_name = cursor.fetchone()[0]
        print(f"Connected to PostgreSQL database {database_name}; applying schema migrations", flush=True)
        run_psql("/database/bootstrap.sql", migration_url, "seed_synthetic=false")
        verify_schema(connection)
        configure_accounts(connection, admin_email, admin_password)
        if seed:
            run_psql("/database/seed.sql", migration_url)
        print("Schema migrations and deployment bootstrap completed successfully", flush=True)
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(26189,42)")
    finally:
        connection.close()


if __name__ == "__main__":
    main()

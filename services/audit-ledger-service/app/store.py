"""Durable SHA-256 audit chain with database-serialized append operations.

PostgreSQL is the deployment backend. SQLite supports isolated local tests using
the same schema and hash computation. This is tamper evidence, not consensus:
an administrator who rewrites the entire database needs an independently saved
checkpoint to be detected.
"""

import hashlib
import hmac
import json
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
    text,
)

from app.models import (
    AppendRequest,
    ChainResponse,
    LedgerRecord,
    VerificationResponse,
    canonical_json,
)

GENESIS = "0" * 64
metadata = MetaData()
entries = Table(
    "ledger_entries", metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=False),
    Column("id", String(36), nullable=False, unique=True),
    Column("version", Integer, nullable=False),
    Column("record_id", String(200), nullable=False, index=True),
    Column("case_id", String(200), index=True),
    Column("actor", String(200), nullable=False),
    Column("action", String(100), nullable=False),
    Column("resource_type", String(100), nullable=False),
    Column("payload", Text, nullable=False),
    Column("timestamp", String(40), nullable=False),
    Column("previous_hash", String(64), nullable=False),
    Column("hash", String(64), nullable=False, unique=True),
)
head = Table(
    "ledger_head", metadata,
    Column("id", Integer, primary_key=True),
    Column("sequence", Integer, nullable=False),
    Column("hash", String(64), nullable=False),
)


class EventConflict(ValueError):
    """The caller reused an event ID for different data."""


class ChainCorrupted(RuntimeError):
    """Appending to a damaged chain must fail closed."""


def record_hash(record: dict) -> str:
    body = {key: value for key, value in record.items() if key != "hash"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def decode_row(row) -> dict:
    result = dict(row)
    result["payload"] = json.loads(result["payload"])
    return result


class LedgerStore:
    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        self.dialect = self.engine.dialect.name
        if self.dialect not in {"postgresql", "sqlite"}:
            raise ValueError("Unsupported ledger database")

    @contextmanager
    def transaction(self):
        with self.engine.connect() as connection:
            try:
                if self.dialect == "sqlite":
                    connection.exec_driver_sql("PRAGMA busy_timeout=30000")
                    connection.exec_driver_sql("BEGIN IMMEDIATE")
                else:
                    connection.begin()
                    connection.execute(text("SELECT pg_advisory_xact_lock(26189, 1)"))
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    def initialize(self) -> None:
        metadata.create_all(self.engine)
        with self.transaction() as connection:
            connection.execute(text(
                "INSERT INTO ledger_head (id,sequence,hash) VALUES (1,0,:genesis) ON CONFLICT (id) DO NOTHING"
            ), {"genesis": GENESIS})
            if self.dialect == "sqlite":
                for operation in ("UPDATE", "DELETE"):
                    connection.exec_driver_sql(
                        f"CREATE TRIGGER IF NOT EXISTS ledger_no_{operation.lower()} "
                        f"BEFORE {operation} ON ledger_entries BEGIN "
                        "SELECT RAISE(ABORT, 'audit entries are append-only'); END"
                    )
            else:
                connection.exec_driver_sql("""
                    CREATE OR REPLACE FUNCTION ledger_reject_mutation() RETURNS trigger AS $$
                    BEGIN RAISE EXCEPTION 'audit entries are append-only'; END;
                    $$ LANGUAGE plpgsql
                """)
                exists = connection.execute(text(
                    "SELECT 1 FROM pg_trigger WHERE tgname='ledger_append_only' "
                    "AND tgrelid='ledger_entries'::regclass"
                )).scalar()
                if not exists:
                    connection.exec_driver_sql(
                        "CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE OR TRUNCATE "
                        "ON ledger_entries FOR EACH STATEMENT EXECUTE FUNCTION ledger_reject_mutation()"
                    )

    def healthy(self) -> bool:
        with self.engine.connect() as connection:
            return connection.execute(select(head.c.id).where(head.c.id == 1)).scalar() == 1

    def assert_ready(self) -> None:
        """Fail closed when the one-time migration job did not prepare storage."""
        with self.engine.connect() as connection:
            if self.dialect == "sqlite":
                required = {"ledger_entries", "ledger_head"}
                present = set(connection.exec_driver_sql(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).scalars())
                if not required.issubset(present) or not self.healthy():
                    raise RuntimeError("Ledger schema migration is missing")
                return
            ready = connection.execute(text("""SELECT
                to_regclass('ledger_entries') IS NOT NULL
                AND to_regclass('ledger_head') IS NOT NULL
                AND EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='ledger_append_only'
                            AND tgrelid=to_regclass('ledger_entries') AND tgenabled='O')
                AND EXISTS (SELECT 1 FROM ledger_head WHERE id=1)""")).scalar_one()
            if not ready:
                raise RuntimeError("Ledger schema migration or append-only protection is missing")

    def append(self, request: AppendRequest) -> LedgerRecord:
        return self.append_many([request])[0]

    def append_many(self, requests: list[AppendRequest]) -> list[LedgerRecord]:
        """Append an ordered batch under one database lock and transaction."""
        if not requests or len(requests) > 500:
            raise ValueError("A ledger batch must contain 1 to 500 events")
        event_ids = [str(request.event_id) for request in requests]
        if len(event_ids) != len(set(event_ids)):
            raise EventConflict("A ledger batch cannot contain duplicate event IDs")
        with self.transaction() as connection:
            existing_rows = connection.execute(
                select(entries).where(entries.c.id.in_(event_ids))
            ).mappings()
            existing = {row["id"]: decode_row(row) for row in existing_rows}
            current = connection.execute(select(head).where(head.c.id == 1)).mappings().one()
            previous = connection.execute(select(entries).order_by(entries.c.sequence.desc()).limit(1)).mappings().first()
            if previous:
                previous = decode_row(previous)
                if (current["sequence"] != previous["sequence"] or current["hash"] != previous["hash"]
                        or record_hash(previous) != previous["hash"]):
                    raise ChainCorrupted("Ledger head is inconsistent")
            elif current["sequence"] != 0 or current["hash"] != GENESIS:
                raise ChainCorrupted("Ledger head references missing entries")
            sequence = current["sequence"]
            previous_hash = current["hash"]
            records: list[LedgerRecord] = []
            inserts = []
            for request, event_id in zip(requests, event_ids, strict=True):
                immutable = request.model_dump(mode="json", exclude={"event_id"})
                if event_id in existing:
                    decoded = existing[event_id]
                    if canonical_json({key: decoded[key] for key in immutable}) != canonical_json(immutable):
                        raise EventConflict("An event ID cannot be reused with different data")
                    if not hmac.compare_digest(record_hash(decoded), decoded["hash"]):
                        raise ChainCorrupted("Stored event hash does not match its data")
                    records.append(LedgerRecord(**decoded))
                    continue
                sequence += 1
                record = {
                    "version": 1, "sequence": sequence, "id": event_id, **immutable,
                    "timestamp": datetime.now(UTC).isoformat(timespec="microseconds"),
                    "previous_hash": previous_hash,
                }
                record["hash"] = record_hash(record)
                previous_hash = record["hash"]
                inserts.append({**record, "payload": canonical_json(record["payload"])})
                records.append(LedgerRecord(**record))
            if inserts:
                connection.execute(entries.insert(), inserts)
                connection.execute(
                    head.update().where(head.c.id == 1).values(sequence=sequence, hash=previous_hash)
                )
            return records

    def list_records(self, limit: int = 50, offset: int = 0, case_ids: list[str] | None = None) -> ChainResponse:
        condition = entries.c.case_id.in_(case_ids) if case_ids is not None else True
        with self.engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(entries).where(condition)).scalar_one()
            rows = connection.execute(select(entries).where(condition).order_by(entries.c.sequence.desc()).limit(limit).offset(offset)).mappings()
            return ChainResponse(records=[LedgerRecord(**decode_row(row)) for row in rows], total=count, limit=limit, offset=offset)

    def verify(self, record_id: str, case_ids: list[str] | None = None) -> VerificationResponse:
        # A shared snapshot prevents a concurrent append from creating a false failure.
        with self.transaction() as connection:
            query = select(entries).where((entries.c.id == record_id) | (entries.c.record_id == record_id))
            if case_ids is not None:
                query = query.where(entries.c.case_id.in_(case_ids))
            target = connection.execute(query.order_by(entries.c.sequence.desc()).limit(1)).mappings().first()
            if not target:
                raise KeyError("Audit record not found")
            checkpoint = connection.execute(select(head).where(head.c.id == 1)).mappings().one()
            expected_sequence = 1
            previous_hash = GENESIS
            error_sequence = None
            checked = 0
            for row in connection.execute(select(entries).order_by(entries.c.sequence)).mappings():
                checked += 1
                try:
                    record = decode_row(row)
                    valid = (
                        record["sequence"] == expected_sequence
                        and record["previous_hash"] == previous_hash
                        and hmac.compare_digest(record_hash(record), record["hash"])
                    )
                except (ValueError, TypeError, RecursionError):
                    valid = False
                if not valid:
                    error_sequence = expected_sequence
                    break
                previous_hash = record["hash"]
                expected_sequence += 1
            if error_sequence is None and (checkpoint["sequence"] != checked or checkpoint["hash"] != previous_hash):
                error_sequence = expected_sequence
            valid = error_sequence is None
            return VerificationResponse(
                record_id=record_id, event_id=target["id"], case_id=target["case_id"],
                verified=valid, status="VERIFIED" if valid else "TAMPERED",
                checked_records=checked, checked_through=checkpoint["sequence"],
                checkpoint_hash=checkpoint["hash"], error_sequence=error_sequence,
                message=(
                    "Stored audit chain matches its checkpoint. This does not verify current source data, "
                    "evidence truth, or a privileged rewrite of both chain and checkpoint."
                    if valid else "Audit chain integrity check failed. Preserve the database for investigation."
                ),
            )

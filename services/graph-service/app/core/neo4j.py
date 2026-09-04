"""CrimeLensAI Graph Service — Neo4j connection lifecycle."""

from __future__ import annotations

import logging
from typing import Any

from neo4j import GraphDatabase, Driver
from neo4j.exceptions import ServiceUnavailable, AuthError

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class Neo4jConnectionManager:
    """Manages a single shared Neo4j driver with startup/shutdown lifecycle."""

    def __init__(self) -> None:
        self._driver: Driver | None = None

    def connect(self) -> None:
        """Create driver, verify connectivity, and ensure constraints."""
        settings = get_settings()
        try:
            self._driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            )
            self._driver.verify_connectivity()
            logger.info("Neo4j connection established: %s", settings.NEO4J_URI)
            self._ensure_constraints()
        except ServiceUnavailable as exc:
            logger.error("Neo4j unavailable at %s: %s", settings.NEO4J_URI, exc)
            self._driver = None
            raise
        except AuthError as exc:
            logger.error("Neo4j authentication failed: %s", exc)
            self._driver = None
            raise

    def close(self) -> None:
        """Close the driver and release resources."""
        if self._driver is not None:
            self._driver.close()
            self._driver = None
            logger.info("Neo4j connection closed")

    @property
    def driver(self) -> Driver:
        """Access the shared driver; raises if not initialized."""
        if self._driver is None:
            raise RuntimeError(
                "Neo4j driver not initialized. Call connect() first."
            )
        return self._driver

    def get_session(self):
        """Convenience: open a new session from the shared driver."""
        return self.driver.session()

    def verify_connectivity(self) -> bool:
        """Return True if Neo4j is reachable, False otherwise."""
        try:
            self.driver.verify_connectivity()
            return True
        except Exception:
            return False

    def execute_query(
        self, query: str, parameters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Run a read query and return all records as dicts."""
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [record.data() for record in result]

    def _ensure_constraints(self) -> None:
        """Create uniqueness constraints and indexes on startup."""
        queries = [
            "CREATE CONSTRAINT case_id_unique IF NOT EXISTS "
            "FOR (c:Case) REQUIRE c.case_id IS UNIQUE",
            "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS "
            "FOR (e:Entity) REQUIRE e.id IS UNIQUE",
            "CREATE CONSTRAINT alert_id_unique IF NOT EXISTS "
            "FOR (a:LinkAlert) REQUIRE a.id IS UNIQUE",
            "CREATE INDEX entity_canonical_lookup IF NOT EXISTS "
            "FOR (e:Entity) ON (e.entity_type, e.canonical_value)",
        ]
        with self.driver.session() as session:
            for q in queries:
                try:
                    session.run(q)
                except Exception as exc:
                    logger.warning("Constraint creation warning: %s", exc)
        logger.info("Neo4j constraints ensured")


# Singleton instance
neo4j_manager = Neo4jConnectionManager()

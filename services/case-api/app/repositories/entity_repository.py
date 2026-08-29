"""
CrimeLensAI — Entity Repository
==================================
In-memory persistence layer for extracted entities, keyed by case_id.
"""

from typing import Dict, List

from app.schemas.entity import ExtractedEntity


class EntityRepository:
    """In-memory entity store keyed by case_id."""

    def __init__(self) -> None:
        self._store: Dict[str, List[ExtractedEntity]] = {}

    def save(self, case_id: str, entities: List[ExtractedEntity]) -> None:
        """Save (overwrite) entities for a case."""
        self._store[case_id] = entities

    def get(self, case_id: str) -> List[ExtractedEntity]:
        """Return entities for a case (empty list if none)."""
        return self._store.get(case_id, [])

    def count(self) -> int:
        """Total entity count across all cases."""
        return sum(len(v) for v in self._store.values())

    def search(self, query: str) -> List[ExtractedEntity]:
        """Search entities by value substring."""
        q = query.lower()
        results = []
        for entities in self._store.values():
            for e in entities:
                if q in e.value.lower():
                    results.append(e)
        return results

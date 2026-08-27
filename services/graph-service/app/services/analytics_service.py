"""CrimeLensAI Graph Service — network analytics (centrality, communities, shortest path)."""

from app.store import InMemoryGraphStore
from app.models.schemas import (
    CentralityResponse, CentralityMetrics,
    CommunityResponse, Community, CommunityMember,
    ShortestPathResponse, PathStep,
)


class AnalyticsService:
    """Wraps the InMemoryGraphStore's NetworkX analytics with typed models."""

    def __init__(self, store: InMemoryGraphStore) -> None:
        self._store = store

    def get_centrality(self, entity_id: str) -> CentralityResponse:
        """Compute centrality metrics for an entity node."""
        result = self._store.centrality(entity_id)
        # Store returns {"entity_id", "centrality": {"degree", "betweenness", "pagerank"}, "explanation"}
        centrality_data = result["centrality"]
        metrics = CentralityMetrics(
            degree=centrality_data["degree"],
            betweenness=centrality_data["betweenness"],
            pagerank=centrality_data["pagerank"],
        )
        return CentralityResponse(
            entity_id=entity_id,
            centrality=metrics,
            explanation=result.get(
                "explanation",
                "High betweenness highlights bridge entities connecting otherwise separate case clusters.",
            ),
        )

    def detect_communities(self) -> CommunityResponse:
        """Run community detection on the entity graph."""
        result = self._store.communities()
        # Store returns {"communities": [{"community_id", "members": [str], "case_ids", "entity_ids"}], "method"}
        communities: list[Community] = []

        for c in result.get("communities", []):
            members: list[CommunityMember] = []
            # members from store are plain entity/case ID strings
            entity_ids = c.get("entity_ids", [])
            case_ids = c.get("case_ids", [])

            for eid in entity_ids:
                entity = self._store.entities.get(eid)
                if entity:
                    members.append(CommunityMember(
                        entity_id=eid,
                        entity_type=entity["entity_type"],
                        value=entity["value"],
                    ))

            entity_types = {m.entity_type for m in members}
            summary = (
                f"Community {c['community_id']} with {len(members)} entities "
                f"across {len(case_ids)} case(s). "
                f"Entity types: {', '.join(sorted(entity_types))}."
                if members else
                f"Community {c['community_id']} with {len(c.get('members', []))} node(s)."
            )

            communities.append(Community(
                community_id=c["community_id"],
                members=members,
                case_ids=case_ids,
                size=len(members) if members else len(c.get("members", [])),
                summary=summary,
            ))

        return CommunityResponse(
            communities=communities,
            method=result.get("method", "greedy_modularity"),
            total_communities=len(communities),
        )

    def get_shortest_path(self, entity_a: str, entity_b: str) -> ShortestPathResponse:
        """Find the shortest path between two entities."""
        result = self._store.shortest_path(entity_a, entity_b)
        # Store returns {"entity_a", "entity_b", "path": [ids], "steps": [{source, target, relationship_type, confidence}], "explanation"}

        steps: list[PathStep] = []
        path = result.get("path", [])

        for step in result.get("steps", []):
            # Get labels for source and target
            source_id = step["source"]
            target_id = step["target"]
            source_entity = self._store.entities.get(source_id)
            target_entity = self._store.entities.get(target_id)

            steps.append(PathStep(
                source=source_id,
                target=target_id,
                source_label=source_entity["value"] if source_entity else source_id,
                target_label=target_entity["value"] if target_entity else target_id,
                relationship_type=step.get("relationship_type"),
                confidence=step.get("confidence"),
            ))

        explanation = result.get("explanation", "")
        if not explanation and path:
            labels = []
            for node_id in path:
                entity = self._store.entities.get(node_id)
                labels.append(entity["value"] if entity else node_id)
            explanation = " → ".join(labels)

        return ShortestPathResponse(
            entity_a=entity_a,
            entity_b=entity_b,
            path=path,
            steps=steps,
            path_length=len(steps),
            explanation=explanation,
        )

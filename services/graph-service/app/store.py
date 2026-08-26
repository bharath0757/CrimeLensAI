"""Graph persistence and explainable network analytics.

The in-memory backend is deterministic and supports tests/demo mode. When
``GRAPH_BACKEND=neo4j`` is configured, the same operations are mirrored to
Neo4j and hydrated on startup. Analytics remain portable NetworkX algorithms,
so the prototype does not require a paid Neo4j/GDS edition to demonstrate its
core intelligence.
"""

from __future__ import annotations

import math
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from itertools import combinations
from typing import Any

import networkx as nx

from .models import AlertStatus, EntityInput, EntityType, RelationshipInput


ENTITY_WEIGHTS = {
    EntityType.PHONE.value: 1.0,
    EntityType.UPI_ID.value: 1.0,
    EntityType.VEHICLE.value: 0.95,
    EntityType.PERSON.value: 0.65,
    EntityType.ORG.value: 0.45,
    EntityType.LOCATION.value: 0.25,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonicalize(entity_type: str, value: str) -> str:
    if entity_type == EntityType.PHONE.value:
        return re.sub(r"\D", "", value)[-10:]
    if entity_type == EntityType.VEHICLE.value:
        return re.sub(r"[^A-Z0-9]", "", value.upper())
    if entity_type == EntityType.UPI_ID.value:
        return value.strip().lower()
    return re.sub(r"\s+", " ", value).strip().casefold()


class InMemoryGraphStore:
    def __init__(self) -> None:
        self.entities: dict[str, dict[str, Any]] = {}
        self.canonical_index: dict[tuple[str, str], str] = {}
        self.case_entities: dict[str, set[str]] = defaultdict(set)
        self.relationships: dict[str, dict[str, Any]] = {}
        self.alerts: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def upsert_entity(self, payload: EntityInput) -> dict[str, Any]:
        with self._lock:
            entity_type = payload.entity_type.value
            canonical = canonicalize(entity_type, payload.canonical_value or payload.value)
            key = (entity_type, canonical)
            entity_id = self.canonical_index.get(key) or payload.id or str(
                uuid.uuid5(uuid.NAMESPACE_URL, f"crimelens:entity:{entity_type}:{canonical}")
            )
            existing_cases = sorted(case for case, ids in self.case_entities.items() if entity_id in ids)
            entity = self.entities.setdefault(entity_id, {
                "id": entity_id,
                "entity_type": entity_type,
                "value": payload.value,
                "canonical_value": canonical,
                "confidence": payload.confidence,
                "occurrences": [],
            })
            entity["confidence"] = max(entity["confidence"], payload.confidence)
            occurrence = {
                "case_id": payload.case_id,
                "source_field": payload.source_field,
                "start_offset": payload.start_offset,
                "end_offset": payload.end_offset,
                "confidence": payload.confidence,
                "observed_value": payload.value,
            }
            occurrence_key = (payload.case_id, payload.source_field, payload.start_offset, payload.end_offset)
            if occurrence_key not in {
                (item["case_id"], item["source_field"], item["start_offset"], item["end_offset"])
                for item in entity["occurrences"]
            }:
                entity["occurrences"].append(occurrence)
            self.entities[entity_id] = entity
            self.canonical_index[key] = entity_id
            self.case_entities[payload.case_id].add(entity_id)

            changed_alerts = []
            for other_case in existing_cases:
                if other_case != payload.case_id:
                    changed_alerts.append(self._upsert_alert(other_case, payload.case_id, entity_id))
            return {"entity": entity, "alerts": changed_alerts}

    def _upsert_alert(self, case_a: str, case_b: str, entity_id: str) -> dict[str, Any]:
        cases = sorted([case_a, case_b])
        alert_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"crimelens:alert:{cases[0]}:{cases[1]}"))
        alert = self.alerts.get(alert_id, {
            "id": alert_id,
            "case_ids": cases,
            "shared_entity_ids": [],
            "severity": "LOW",
            "status": AlertStatus.NEW.value,
            "title": "New cross-case connection",
            "explanation": "",
            "created_at": utc_now(),
        })
        if entity_id not in alert["shared_entity_ids"]:
            alert["shared_entity_ids"].append(entity_id)
        shared = [self.entities[item] for item in alert["shared_entity_ids"]]
        types = {item["entity_type"] for item in shared}
        strongest = max((ENTITY_WEIGHTS.get(item["entity_type"], 0.2) for item in shared), default=0.0)
        alert["severity"] = "HIGH" if strongest >= 0.95 or len(types) >= 2 else "MEDIUM" if strongest >= 0.6 else "LOW"
        summary = ", ".join(f'{item["entity_type"]} {item["value"]}' for item in shared[:3])
        alert["explanation"] = (
            f"Cases {cases[0]} and {cases[1]} share {len(shared)} observed entity signal(s): {summary}. "
            "Open the source occurrences before treating this as an investigative conclusion."
        )
        self.alerts[alert_id] = alert
        self._persist_alert(alert)
        return alert

    def create_relationship(self, payload: RelationshipInput) -> dict[str, Any]:
        with self._lock:
            if payload.source_entity_id not in self.entities or payload.target_entity_id not in self.entities:
                raise KeyError("Both relationship endpoints must exist")
            relation_id = payload.id or str(uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"crimelens:relationship:{payload.source_entity_id}:{payload.target_entity_id}:"
                f"{payload.relationship_type}:{payload.source_case_id}:{payload.evidence_record_id or ''}",
            ))
            relation = {"id": relation_id, **payload.model_dump(exclude={"id"})}
            self.relationships[relation_id] = relation
            self._persist_relationship(relation)
            return relation

    def get_linkage(self, case_id: str) -> dict[str, Any]:
        own = self.case_entities.get(case_id, set())
        linked = []
        for other_case, other_entities in self.case_entities.items():
            if other_case == case_id:
                continue
            shared_ids = sorted(own & other_entities)
            if not shared_ids:
                continue
            shared = [self.entities[item] for item in shared_ids]
            raw_strength = sum(
                ENTITY_WEIGHTS.get(item["entity_type"], 0.2) * item["confidence"] for item in shared
            )
            strength = round(min(0.99, 1 - math.exp(-raw_strength)), 4)
            signals = ", ".join(f'{item["entity_type"]} {item["value"]}' for item in shared)
            linked.append({
                "case_id": other_case,
                "shared_entities": shared,
                "link_strength": strength,
                "explanation": (
                    f"Linked because both cases contain {signals}. Score combines entity specificity and "
                    "source confidence; it prioritises review and is not proof of identity or guilt."
                ),
            })
        linked.sort(key=lambda item: (-item["link_strength"], item["case_id"]))
        return {"case_id": case_id, "linked_cases": linked, "graph": self.subgraph_for_case(case_id)}

    def subgraph_for_case(self, case_id: str) -> dict[str, Any]:
        case_ids = {case_id}
        own = self.case_entities.get(case_id, set())
        for other_case, entity_ids in self.case_entities.items():
            if own & entity_ids:
                case_ids.add(other_case)
        entity_ids = set().union(*(self.case_entities.get(item, set()) for item in case_ids)) if case_ids else set()
        nodes = [{"id": item, "label": item, "type": "CASE", "metadata": {}} for item in sorted(case_ids)]
        nodes.extend({
            "id": entity_id,
            "label": self.entities[entity_id]["value"],
            "type": self.entities[entity_id]["entity_type"],
            "metadata": {"confidence": self.entities[entity_id]["confidence"]},
        } for entity_id in sorted(entity_ids))
        edges = []
        for current_case in sorted(case_ids):
            for entity_id in sorted(self.case_entities.get(current_case, set()) & entity_ids):
                edges.append({"source": current_case, "target": entity_id, "label": "HAS_ENTITY", "weight": 1.0})
        for relation in self.relationships.values():
            if relation["source_entity_id"] in entity_ids and relation["target_entity_id"] in entity_ids:
                edges.append({
                    "source": relation["source_entity_id"], "target": relation["target_entity_id"],
                    "label": relation["relationship_type"], "weight": relation["confidence"],
                    "why_linked": relation["why_linked"],
                })
        return {"nodes": nodes, "edges": edges}

    def _network(self, include_cases: bool = True) -> nx.Graph:
        graph = nx.Graph()
        for entity_id, entity in self.entities.items():
            graph.add_node(entity_id, type=entity["entity_type"], label=entity["value"])
        for case_id, entity_ids in self.case_entities.items():
            if include_cases:
                graph.add_node(case_id, type="CASE", label=case_id)
                for entity_id in entity_ids:
                    graph.add_edge(case_id, entity_id, relationship_type="HAS_ENTITY", confidence=1.0)
            else:
                for a, b in combinations(sorted(entity_ids), 2):
                    if graph.has_edge(a, b):
                        graph[a][b]["case_ids"].add(case_id)
                    else:
                        graph.add_edge(a, b, relationship_type="CO_OCCURS", confidence=0.65, case_ids={case_id})
        for relation in self.relationships.values():
            graph.add_edge(
                relation["source_entity_id"], relation["target_entity_id"],
                relationship_type=relation["relationship_type"], confidence=relation["confidence"],
                case_ids={relation["source_case_id"]}, why_linked=relation["why_linked"],
            )
        return graph

    def centrality(self, entity_id: str) -> dict[str, Any]:
        graph = self._network(include_cases=True)
        if entity_id not in graph:
            raise KeyError("Entity not found")
        degree = nx.degree_centrality(graph).get(entity_id, 0.0)
        betweenness = nx.betweenness_centrality(graph).get(entity_id, 0.0)
        pagerank = nx.pagerank(graph).get(entity_id, 0.0)
        return {
            "entity_id": entity_id,
            "centrality": {"degree": round(degree, 6), "betweenness": round(betweenness, 6), "pagerank": round(pagerank, 6)},
            "explanation": "High betweenness highlights bridge entities connecting otherwise separate case clusters.",
        }

    def communities(self) -> dict[str, Any]:
        graph = self._network(include_cases=True)
        if graph.number_of_nodes() == 0:
            return {"communities": []}
        components = []
        for component in nx.connected_components(graph):
            subgraph = graph.subgraph(component)
            if subgraph.number_of_edges() == 0:
                groups = [set(component)]
            else:
                groups = list(nx.community.greedy_modularity_communities(subgraph))
            components.extend(groups)
        result = []
        for index, members in enumerate(sorted(components, key=lambda group: (-len(group), sorted(group)[0])), start=1):
            result.append({
                "community_id": index,
                "members": sorted(members),
                "case_ids": sorted(item for item in members if item in self.case_entities),
                "entity_ids": sorted(item for item in members if item in self.entities),
            })
        return {"communities": result, "method": "greedy_modularity"}

    def shortest_path(self, entity_a: str, entity_b: str) -> dict[str, Any]:
        graph = self._network(include_cases=True)
        if entity_a not in graph or entity_b not in graph:
            raise KeyError("One or both entities were not found")
        try:
            path = nx.shortest_path(graph, entity_a, entity_b)
        except nx.NetworkXNoPath as exc:
            raise ValueError("No path exists between the supplied entities") from exc
        steps = []
        for source, target in zip(path, path[1:]):
            edge = graph[source][target]
            steps.append({"source": source, "target": target, "relationship_type": edge.get("relationship_type"), "confidence": edge.get("confidence")})
        labels = [graph.nodes[item].get("label", item) for item in path]
        return {
            "entity_a": entity_a, "entity_b": entity_b, "path": path, "steps": steps,
            "explanation": " -> ".join(labels),
        }

    def patterns(self, case_id: str) -> dict[str, Any]:
        patterns = []
        linkage = self.get_linkage(case_id)["linked_cases"]
        for link in linkage:
            types = {entity["entity_type"] for entity in link["shared_entities"]}
            pattern_type = "MULTI_SIGNAL_CONVERGENCE" if len(types) >= 2 else "REPEATED_IDENTIFIER"
            patterns.append({
                "pattern_type": pattern_type,
                "case_ids": [case_id, link["case_id"]],
                "confidence": link["link_strength"],
                "supporting_entity_ids": [entity["id"] for entity in link["shared_entities"]],
                "explanation": link["explanation"],
                "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            })
        for entity_id in self.case_entities.get(case_id, set()):
            connected_cases = sorted(case for case, ids in self.case_entities.items() if entity_id in ids)
            if len(connected_cases) >= 3:
                entity = self.entities[entity_id]
                patterns.append({
                    "pattern_type": "BRIDGE_ENTITY",
                    "case_ids": connected_cases,
                    "confidence": round(min(0.99, 0.55 + 0.1 * len(connected_cases)), 4),
                    "supporting_entity_ids": [entity_id],
                    "explanation": f'{entity["entity_type"]} {entity["value"]} appears across {len(connected_cases)} cases and may bridge jurisdictions.',
                    "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
                })
        patterns.sort(key=lambda item: (-item["confidence"], item["pattern_type"]))
        return {"case_id": case_id, "patterns": patterns}

    def link_predictions(self, limit: int = 20, min_score: float = 0.2) -> dict[str, Any]:
        graph = self._network(include_cases=False)
        predictions = []
        nodes = sorted(graph.nodes)
        for a, b in combinations(nodes, 2):
            if graph.has_edge(a, b):
                continue
            common = sorted(nx.common_neighbors(graph, a, b))
            if not common:
                continue
            union = set(graph.neighbors(a)) | set(graph.neighbors(b))
            jaccard = len(common) / len(union) if union else 0.0
            adamic = sum(1 / math.log(max(2, graph.degree(node))) for node in common)
            score = min(0.95, 0.7 * jaccard + 0.3 * (1 - math.exp(-adamic)))
            if score < min_score:
                continue
            predictions.append({
                "source_entity_id": a,
                "target_entity_id": b,
                "confidence": round(score, 4),
                "common_neighbor_ids": common,
                "method": "jaccard_plus_adamic_adar",
                "explanation": f"Candidate missing link supported by {len(common)} common neighbour(s). Review their source records before action.",
                "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            })
        predictions.sort(key=lambda item: (-item["confidence"], item["source_entity_id"], item["target_entity_id"]))
        return {"predictions": predictions[:limit]}

    def list_alerts(self, case_id: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
        alerts = list(self.alerts.values())
        if case_id:
            alerts = [alert for alert in alerts if case_id in alert["case_ids"]]
        if status:
            alerts = [alert for alert in alerts if alert["status"] == status]
        return sorted(alerts, key=lambda alert: (alert["status"] != AlertStatus.NEW.value, alert["created_at"]), reverse=False)

    def acknowledge_alert(self, alert_id: str) -> dict[str, Any]:
        if alert_id not in self.alerts:
            raise KeyError("Alert not found")
        self.alerts[alert_id]["status"] = AlertStatus.ACKNOWLEDGED.value
        self._persist_alert(self.alerts[alert_id])
        return self.alerts[alert_id]

    # Hooks used by the Neo4j-backed subclass.
    def _persist_entity(self, entity: dict[str, Any], case_id: str) -> None:
        return None

    def _persist_relationship(self, relation: dict[str, Any]) -> None:
        return None

    def _persist_alert(self, alert: dict[str, Any]) -> None:
        return None


class Neo4jGraphStore(InMemoryGraphStore):
    """Neo4j persistence with portable in-process analytics."""

    def __init__(self, uri: str, user: str, password: str) -> None:
        super().__init__()
        from neo4j import GraphDatabase

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver.verify_connectivity()
        self._hydrate()

    def _hydrate(self) -> None:
        with self.driver.session() as session:
            rows = session.run(
                "MATCH (c:Case)-[o:HAS_ENTITY]->(e:Entity) RETURN c.case_id AS case_id, e, properties(o) AS occurrence"
            )
            for row in rows:
                data = dict(row["e"])
                entity_id = data["id"]
                entity = self.entities.setdefault(entity_id, {**data, "occurrences": []})
                entity["occurrences"].append({"case_id": row["case_id"], **row["occurrence"]})
                self.canonical_index[(data["entity_type"], data["canonical_value"])] = entity_id
                self.case_entities[row["case_id"]].add(entity_id)
            rows = session.run(
                "MATCH (a:Entity)-[r:RELATED]->(b:Entity) RETURN a.id AS source, b.id AS target, properties(r) AS relation"
            )
            for row in rows:
                relation = dict(row["relation"])
                relation.update(source_entity_id=row["source"], target_entity_id=row["target"])
                self.relationships[relation["id"]] = relation
            rows = session.run("MATCH (a:LinkAlert) RETURN properties(a) AS alert")
            for row in rows:
                alert = dict(row["alert"])
                alert["case_ids"] = list(alert.get("case_ids", []))
                alert["shared_entity_ids"] = list(alert.get("shared_entity_ids", []))
                self.alerts[alert["id"]] = alert

    def upsert_entity(self, payload: EntityInput) -> dict[str, Any]:
        result = super().upsert_entity(payload)
        self._persist_entity(result["entity"], payload.case_id)
        return result

    def _persist_entity(self, entity: dict[str, Any], case_id: str) -> None:
        occurrence = next(item for item in reversed(entity["occurrences"]) if item["case_id"] == case_id)
        with self.driver.session() as session:
            session.run(
                "MERGE (c:Case {case_id:$case_id}) "
                "MERGE (e:Entity {id:$id}) SET e.entity_type=$entity_type, e.value=$value, "
                "e.canonical_value=$canonical_value, e.confidence=$confidence "
                "MERGE (c)-[o:HAS_ENTITY]->(e) SET o += $occurrence",
                case_id=case_id, id=entity["id"], entity_type=entity["entity_type"], value=entity["value"],
                canonical_value=entity["canonical_value"], confidence=entity["confidence"], occurrence=occurrence,
            )

    def _persist_relationship(self, relation: dict[str, Any]) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (a:Entity {id:$source}), (b:Entity {id:$target}) "
                "MERGE (a)-[r:RELATED {id:$id}]->(b) SET r += $properties",
                source=relation["source_entity_id"], target=relation["target_entity_id"], id=relation["id"],
                properties={key: value for key, value in relation.items() if key not in {"source_entity_id", "target_entity_id"}},
            )

    def _persist_alert(self, alert: dict[str, Any]) -> None:
        with self.driver.session() as session:
            session.run("MERGE (a:LinkAlert {id:$id}) SET a += $properties", id=alert["id"], properties=alert)


def build_store() -> InMemoryGraphStore:
    if os.getenv("GRAPH_BACKEND", "memory").lower() != "neo4j":
        return InMemoryGraphStore()
    return Neo4jGraphStore(
        os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
        os.getenv("NEO4J_USER", "neo4j"),
        os.getenv("NEO4J_PASSWORD", "neo4j_dev_password"),
    )

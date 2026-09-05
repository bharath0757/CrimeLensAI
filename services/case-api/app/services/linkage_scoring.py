"""Evidence-first five-signal case linkage scoring over PostgreSQL records."""

from __future__ import annotations

import asyncio
import math
import re
from collections import Counter, defaultdict

from sqlalchemy import text

from app.core.config import settings

WEIGHTS = {
    "entity_overlap": 0.30,
    "phone_overlap": 0.25,
    "transaction_overlap": 0.20,
    "location_overlap": 0.10,
    "semantic_similarity": 0.15,
}
STOP_WORDS = {
    "about", "after", "against", "alleged", "case", "complaint", "during",
    "from", "investigation", "officer", "police", "reported", "statement",
    "that", "their", "there", "this", "under", "were", "with",
}


async def enrich_case_linkage(case_id: str, graph_payload: dict) -> dict:
    if settings.DATA_BACKEND != "postgres":
        return graph_payload
    return await asyncio.to_thread(_score_postgres, case_id, graph_payload)


def _score_postgres(case_id: str, graph_payload: dict) -> dict:
    from app.repositories.postgres import get_engine

    with get_engine().connect() as connection:
        case_rows = connection.execute(text(
            "SELECT id,title,description,complaint,coalesce(location,'') AS location FROM cases"
        )).mappings().all()
        if not any(row["id"] == case_id for row in case_rows):
            return graph_payload
        entity_rows = connection.execute(text(
            "SELECT id,case_id,entity_type,name,normalized_value,confidence_score FROM entities "
            "WHERE review_status <> 'REJECTED'"
        )).mappings().all()
        cdr_rows = connection.execute(text(
            "SELECT case_id,caller,receiver,tower FROM cdr_records"
        )).mappings().all()
        transaction_rows = connection.execute(text(
            "SELECT case_id,sender,receiver,upi_id FROM transactions"
        )).mappings().all()

    all_entities = defaultdict(set)
    phones = defaultdict(set)
    transactions = defaultdict(set)
    locations = defaultdict(set)
    entity_display = {}
    for row in entity_rows:
        kind = row["entity_type"]
        value = row["normalized_value"]
        key = f"{kind}:{value}"
        all_entities[row["case_id"]].add(key)
        entity_display[key] = row
        if kind in {"PHONE", "PHONE_NUMBER"}:
            phones[row["case_id"]].add(_identifier(value))
        if kind in {"UPI", "UPI_ID", "BANK", "BANK_ACCOUNT"}:
            transactions[row["case_id"]].add(_identifier(value))
        if kind == "LOCATION":
            locations[row["case_id"]].add(_identifier(value))
    for row in cdr_rows:
        phones[row["case_id"]].update({_identifier(row["caller"]), _identifier(row["receiver"])})
        locations[row["case_id"]].add(_identifier(row["tower"]))
    for row in transaction_rows:
        transactions[row["case_id"]].update(
            {_identifier(row["sender"]), _identifier(row["receiver"]), _identifier(row["upi_id"])}
        )
    narratives = {}
    for row in case_rows:
        narratives[row["id"]] = " ".join(
            str(row[field] or "") for field in ("title", "description", "complaint")
        )
        if row["location"]:
            locations[row["id"]].add(_identifier(row["location"]))
    semantic = _tfidf_vectors(narratives)

    graph_links = {item["case_id"]: item for item in graph_payload.get("linked_cases", [])}
    links = []
    for other_id in sorted(narratives):
        if other_id == case_id:
            continue
        shared_entities = all_entities[case_id] & all_entities[other_id]
        shared_phones = _clean_intersection(phones[case_id], phones[other_id])
        shared_transactions = _clean_intersection(transactions[case_id], transactions[other_id])
        shared_locations = _clean_intersection(locations[case_id], locations[other_id])
        components = {
            "entity_overlap": _overlap(all_entities[case_id], all_entities[other_id]),
            "phone_overlap": _overlap(phones[case_id], phones[other_id]),
            "transaction_overlap": _overlap(transactions[case_id], transactions[other_id]),
            "location_overlap": _overlap(locations[case_id], locations[other_id]),
            "semantic_similarity": _cosine(semantic[case_id], semantic[other_id]),
        }
        score = round(sum(WEIGHTS[name] * value for name, value in components.items()), 4)
        if score < 0.10:
            continue
        graph_link = graph_links.get(other_id, {})
        shared = graph_link.get("shared_entities") or [
            {
                "entity_id": entity_display[key]["id"],
                "entity_type": entity_display[key]["entity_type"],
                "value": entity_display[key]["name"],
                "canonical_value": entity_display[key]["normalized_value"],
                "confidence": entity_display[key]["confidence_score"],
            }
            for key in sorted(shared_entities)
        ]
        evidence = []
        if shared_entities:
            evidence.append(f"{len(shared_entities)} normalized entity match(es)")
        if shared_phones:
            evidence.append(f"{len(shared_phones)} shared phone/CDR identifier(s)")
        if shared_transactions:
            evidence.append(f"{len(shared_transactions)} shared account/UPI transaction identifier(s)")
        if shared_locations:
            evidence.append(f"{len(shared_locations)} shared location/tower signal(s)")
        if components["semantic_similarity"] >= 0.20:
            evidence.append(f"narrative similarity {components['semantic_similarity']:.2f}")
        links.append({
            "case_id": other_id,
            "shared_entities": shared,
            "link_strength": min(score, 0.99),
            "score_components": {key: round(value, 4) for key, value in components.items()},
            "explanation": (
                "Linked for officer review because " + ", ".join(evidence)
                + ". Weighted score: entities 30%, phones 25%, transactions 20%, locations 10%, narrative similarity 15%. "
                "This is an investigative lead, not proof of identity or guilt."
            ),
        })
    links.sort(key=lambda item: (-item["link_strength"], item["case_id"]))
    return {"case_id": case_id, "linked_cases": links, "source": "postgres_five_signal_plus_graph"}


def _identifier(value) -> str:
    return re.sub(r"\s+", "", str(value or "")).casefold()


def _clean_intersection(left: set[str], right: set[str]) -> set[str]:
    return {value for value in left & right if value}


def _overlap(left: set[str], right: set[str]) -> float:
    intersection = _clean_intersection(left, right)
    if not intersection:
        return 0.0
    return min(1.0, len(intersection) / max(1, min(len(left), len(right))))


def _tokens(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.casefold()) if len(token) >= 4 and token not in STOP_WORDS]


def _tfidf_vectors(documents: dict[str, str]) -> dict[str, dict[str, float]]:
    token_counts = {identifier: Counter(_tokens(value)) for identifier, value in documents.items()}
    document_frequency = Counter(token for counts in token_counts.values() for token in counts)
    total = max(1, len(documents))
    return {
        identifier: {
            token: (1 + math.log(count)) * (math.log((1 + total) / (1 + document_frequency[token])) + 1)
            for token, count in counts.items()
        }
        for identifier, counts in token_counts.items()
    }


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(value * right.get(token, 0.0) for token, value in left.items())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    return min(1.0, dot / (left_norm * right_norm)) if left_norm and right_norm else 0.0

"""End-to-end raw FIR analysis for the investigator-facing workflow."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from typing import Any

import httpx

from .models import EntityInput, FirAnalysisRequest
from .store import InMemoryGraphStore

BatchExtractor = Callable[[list[dict[str, Any]]], dict[str, Any]]


class ExtractionServiceClient:
    def __init__(self, base_url: str | None = None, timeout_seconds: float = 30.0) -> None:
        configured = (base_url or os.getenv("EXTRACTION_SERVICE_URL", "http://extraction:8001")).strip().rstrip("/")
        self.base_url = configured if "://" in configured else f"http://{configured}"
        self.timeout_seconds = timeout_seconds

    def extract_batch(self, firs: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/api/v1/extract/batch",
                json={"firs": firs},
                headers={"X-Service-Token": os.getenv("SERVICE_AUTH_TOKEN", "")},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Entity extraction service unavailable: {exc}") from exc


class FirAnalysisService:
    def __init__(self, store: InMemoryGraphStore, extractor: BatchExtractor | None = None) -> None:
        self.store = store
        self.extractor = extractor or ExtractionServiceClient().extract_batch

    def analyze(self, request: FirAnalysisRequest) -> dict[str, Any]:
        fir_payloads = [fir.model_dump() for fir in request.firs]
        extraction = self.extractor(fir_payloads)
        results = extraction.get("results", [])
        if len(results) != len(request.firs):
            raise RuntimeError("Extraction service returned an incomplete FIR batch")

        new_alerts: dict[str, dict[str, Any]] = {}
        case_results = []
        for result in results:
            ingested_entities = []
            for raw_entity in result.get("entities", []):
                entity_payload = EntityInput.model_validate({
                    **raw_entity,
                    "case_id": result["case_id"],
                    "source_field": raw_entity.get("source_field", "fir_text"),
                })
                upsert = self.store.upsert_entity(entity_payload)
                ingested_entities.append(upsert["entity"])
                for alert in upsert["alerts"]:
                    new_alerts[alert["id"]] = alert
            case_results.append({
                "case_id": result["case_id"],
                "district": result.get("district"),
                "fir_number": result.get("fir_number"),
                "entities": ingested_entities,
                "warnings": result.get("warnings", []),
            })

        case_ids = [fir.case_id for fir in request.firs]
        cross_case_links = []
        seen_pairs = set()
        all_patterns = []
        seen_patterns = set()
        for case_id in case_ids:
            linkage = self.store.get_linkage(case_id)
            for link in linkage["linked_cases"]:
                pair = tuple(sorted((case_id, link["case_id"])))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                cross_case_links.append({"case_ids": list(pair), **link})
            for pattern in self.store.patterns(case_id)["patterns"]:
                key = (
                    pattern["pattern_type"],
                    tuple(sorted(pattern["case_ids"])),
                    tuple(sorted(pattern["supporting_entity_ids"])),
                )
                if key not in seen_patterns:
                    seen_patterns.add(key)
                    all_patterns.append(pattern)

        cross_case_links.sort(key=lambda item: (-item["link_strength"], item["case_ids"]))
        all_patterns.sort(key=lambda item: (-item["confidence"], item["pattern_type"]))
        alerts = sorted(new_alerts.values(), key=lambda alert: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[alert["severity"]], alert["created_at"]))
        high_priority = [alert for alert in alerts if alert["severity"] == "HIGH"]

        if high_priority:
            summary = f"{len(high_priority)} high-priority cross-case connection alert(s) require source review."
        elif cross_case_links:
            summary = f"{len(cross_case_links)} cross-case connection(s) were found; review their supporting records."
        else:
            summary = "No cross-case connection was found in the current graph. Retain the extracted entities for future matching."

        return {
            "analysis_run_id": str(uuid.uuid4()),
            "status": "COMPLETED",
            "cases_processed": len(case_results),
            "entities_extracted": sum(len(result["entities"]) for result in case_results),
            "case_results": case_results,
            "alerts": alerts,
            "cross_case_links": cross_case_links,
            "patterns": all_patterns,
            "officer_brief": {
                "summary": summary,
                "recommended_actions": [
                    "Open each alert and verify the original FIR/CDR/transaction occurrence.",
                    "Confirm or reject ambiguous person-name resolutions before merging identities.",
                    "Escalate cross-jurisdiction links through the authorised supervisory workflow.",
                ] if cross_case_links else [
                    "Keep the case active for matching against future FIR, CDR and transaction ingestion."
                ],
                "decision_boundary": "All connections are investigative leads, not findings of guilt.",
            },
            "warnings": extraction.get("warnings", []),
        }

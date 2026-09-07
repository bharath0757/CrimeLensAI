"""
Synthetic and Demo Dataset Loader for CrimeLensAI
Loads the 1,000 synthetic FIR cases, CDRs, transactions, and judge presentation demo pack
into the in-memory repositories for rich local demonstration and analysis.
"""

import csv
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas.case import CasePriority, CaseStatus
from app.schemas.entity import EntityType
from app.schemas.relationship import RelationshipType
from app.integrations.ledger_integration import ledger_service

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[4]

class SyntheticDataLoader:
    def __init__(self):
        self.loaded = False
        self.total_money_flow = 0.0
        self.transaction_timeline: list[dict[str, Any]] = []

    def load_if_needed(self, case_repo, entity_repo, relationship_repo):
        if self.loaded:
            return
        self.load(case_repo, entity_repo, relationship_repo)

    def load(self, case_repo, entity_repo, relationship_repo):
        now = datetime.now(UTC)
        admin_id = "user-admin-001"
        inv_id = "user-inv-002"
        assigned = [admin_id, inv_id]

        # 1. Load Demo FIR Presentation Pack (Judge Presentation Cases)
        demo_firs = [
            {
                "id": "DEMO-FIR-001",
                "case_number": "DEMO-FIR-001",
                "title": "Courier Phishing Network - Lucknow",
                "description": "Complainant received fake courier SMS demanding KYC update. Paid fee via demohub26189@upi. Suspect used phone 9000990189 and fled in vehicle UP 32 AB 2618.",
                "status": CaseStatus.OPEN,
                "priority": CasePriority.HIGH,
                "location": "Lucknow",
                "tags": ["phishing", "cybercrime", "DEMO", "Lucknow"],
                "persons": [("Suresh Sharma", "SUSPECT")],
                "phones": ["9000990189"],
                "vehicles": ["UP 32 AB 2618"],
                "upis": ["demohub26189@upi"],
            },
            {
                "id": "DEMO-FIR-002",
                "case_number": "DEMO-FIR-002",
                "title": "Online Marketplace Fraud - Kanpur",
                "description": "Victim defrauded during used electronics purchase. Seller demanded payment to demohub26189@upi and called from 9000990189. Delivery vehicle noted as UP 32 AB 2618.",
                "status": CaseStatus.IN_PROGRESS,
                "priority": CasePriority.HIGH,
                "location": "Kanpur",
                "tags": ["marketplace_fraud", "cybercrime", "DEMO", "Kanpur"],
                "persons": [("Priya Verma", "SUSPECT")],
                "phones": ["9000990189"],
                "vehicles": ["UP 32 AB 2618"],
                "upis": ["demohub26189@upi"],
            },
            {
                "id": "DEMO-FIR-003",
                "case_number": "DEMO-FIR-003",
                "title": "Mule Account Operation - Hyderabad",
                "description": "Unregistered entity operating financial transfers via mule26189@ybl into account 123456789012 under North Star Trading. Contact number logged as 9876502618.",
                "status": CaseStatus.OPEN,
                "priority": CasePriority.HIGH,
                "location": "Hyderabad",
                "tags": ["mule_account", "money_laundering", "DEMO", "Hyderabad"],
                "persons": [("Rajesh Gupta", "SUSPECT")],
                "phones": ["9876502618"],
                "vehicles": [],
                "upis": ["mule26189@ybl"],
                "accounts": ["123456789012"],
            },
            {
                "id": "DEMO-FIR-004",
                "case_number": "DEMO-FIR-004",
                "title": "Warehouse Call Centre & Logistics - Kanpur",
                "description": "Illegal call operation discovered in Kanpur warehouse. Vehicle UP 32 AB 2618 identified on premises. Phone 9876502618 and transfers to mule26189@ybl recovered.",
                "status": CaseStatus.IN_PROGRESS,
                "priority": CasePriority.CRITICAL,
                "location": "Kanpur",
                "tags": ["call_center", "warehouse", "DEMO", "Kanpur"],
                "persons": [("Vikram Singh", "SUSPECT")],
                "phones": ["9876502618"],
                "vehicles": ["UP 32 AB 2618"],
                "upis": ["mule26189@ybl"],
                "accounts": ["123456789012"],
            },
            {
                "id": "DEMO-FIR-005",
                "case_number": "DEMO-FIR-005",
                "title": "Unrelated Local Petty Theft - Jaipur",
                "description": "Bicycle theft from residential apartment in Jaipur. Suspect fled on foot. Standalone incident with contact number 9123456780 and vehicle RJ 14 XY 9999.",
                "status": CaseStatus.OPEN,
                "priority": CasePriority.MEDIUM,
                "location": "Jaipur",
                "tags": ["theft", "control_case", "DEMO", "Jaipur"],
                "persons": [("Mohan Lal", "SUSPECT")],
                "phones": ["9123456780"],
                "vehicles": ["RJ 14 XY 9999"],
                "upis": [],
            },
        ]

        for dfir in demo_firs:
            cid = dfir["id"]
            case_repo._cases[cid] = {
                "id": cid,
                "case_number": dfir["case_number"],
                "title": dfir["title"],
                "description": dfir["description"],
                "status": dfir["status"],
                "priority": dfir["priority"],
                "owner_id": admin_id,
                "assigned_investigator_ids": assigned,
                "tags": dfir["tags"],
                "document_count": 1,
                "entity_count": 0,
                "relationship_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            # Record CASE_CREATED in hash ledger
            priority_val = dfir["priority"].value if hasattr(dfir["priority"], "value") else str(dfir["priority"])
            ledger_service.local_store.append({
                "event_id": f"ev-case-{cid}",
                "record_id": cid,
                "case_id": cid,
                "actor": admin_id,
                "action": "CASE_CREATED",
                "resource_type": "CASE",
                "payload": {"case_number": dfir["case_number"], "title": dfir["title"], "priority": priority_val},
                "timestamp": now.isoformat(),
            })

            # Add demo entities
            created_ent_ids = []
            for name, role in dfir.get("persons", []):
                eid = f"ent-{cid}-{name.replace(' ', '_').lower()}"
                entity_repo._entities[eid] = {
                    "id": eid,
                    "case_id": cid,
                    "name": name,
                    "entity_type": EntityType.PERSON,
                    "description": f"{role} in {cid}",
                    "properties": {"role": role},
                    "confidence_score": 0.98,
                    "review_status": "CONFIRMED",
                    "created_at": now,
                    "updated_at": now,
                }
                created_ent_ids.append(eid)

            for phone in dfir.get("phones", []):
                eid = f"ent-{cid}-phone-{phone}"
                entity_repo._entities[eid] = {
                    "id": eid,
                    "case_id": cid,
                    "name": phone,
                    "entity_type": EntityType.PHONE_NUMBER,
                    "description": f"Phone identified in {cid}",
                    "properties": {},
                    "confidence_score": 0.99,
                    "review_status": "CONFIRMED",
                    "created_at": now,
                    "updated_at": now,
                }
                created_ent_ids.append(eid)

            for veh in dfir.get("vehicles", []):
                eid = f"ent-{cid}-veh-{veh.replace(' ', '')}"
                entity_repo._entities[eid] = {
                    "id": eid,
                    "case_id": cid,
                    "name": veh,
                    "entity_type": EntityType.VEHICLE,
                    "description": f"Vehicle observed in {cid}",
                    "properties": {},
                    "confidence_score": 0.95,
                    "review_status": "CONFIRMED",
                    "created_at": now,
                    "updated_at": now,
                }
                created_ent_ids.append(eid)

            for upi in dfir.get("upis", []):
                eid = f"ent-{cid}-upi-{upi}"
                entity_repo._entities[eid] = {
                    "id": eid,
                    "case_id": cid,
                    "name": upi,
                    "entity_type": EntityType.UPI_ID,
                    "description": f"UPI handle flagged in {cid}",
                    "properties": {},
                    "confidence_score": 0.99,
                    "review_status": "CONFIRMED",
                    "created_at": now,
                    "updated_at": now,
                }
                created_ent_ids.append(eid)

            for acc in dfir.get("accounts", []):
                eid = f"ent-{cid}-acc-{acc}"
                entity_repo._entities[eid] = {
                    "id": eid,
                    "case_id": cid,
                    "name": acc,
                    "entity_type": EntityType.BANK_ACCOUNT,
                    "description": f"Bank account linked to {cid}",
                    "properties": {},
                    "confidence_score": 0.97,
                    "review_status": "CONFIRMED",
                    "created_at": now,
                    "updated_at": now,
                }
                created_ent_ids.append(eid)

            case_repo._cases[cid]["entity_count"] = len(created_ent_ids)

            for eid in created_ent_ids:
                ent = entity_repo._entities.get(eid)
                if ent:
                    ent_type_val = ent["entity_type"].value if hasattr(ent["entity_type"], "value") else str(ent["entity_type"])
                    ledger_service.local_store.append({
                        "event_id": f"ev-{eid}",
                        "record_id": eid,
                        "case_id": cid,
                        "actor": "system:ai_extractor",
                        "action": "ENTITY_EXTRACTED",
                        "resource_type": "ENTITY",
                        "payload": {"name": ent["name"], "entity_type": ent_type_val, "confidence": ent["confidence_score"]},
                        "timestamp": now.isoformat(),
                    })

            # Create relationships between entities
            if len(created_ent_ids) >= 2:
                primary = created_ent_ids[0]
                for target in created_ent_ids[1:]:
                    rid = f"rel-{cid}-{primary}-{target}"
                    relationship_repo._relationships[rid] = {
                        "id": rid,
                        "case_id": cid,
                        "source_entity_id": primary,
                        "target_entity_id": target,
                        "relationship_type": RelationshipType.ASSOCIATED_WITH,
                        "description": f"Linked evidence in {cid}",
                        "properties": {},
                        "confidence_score": 0.95,
                        "created_at": now,
                        "updated_at": now,
                    }
                    ledger_service.local_store.append({
                        "event_id": f"ev-{rid}",
                        "record_id": rid,
                        "case_id": cid,
                        "actor": "system:linkage_engine",
                        "action": "RELATIONSHIP_CREATED",
                        "resource_type": "RELATIONSHIP",
                        "payload": {"source": primary, "target": target, "type": "ASSOCIATED_WITH"},
                        "timestamp": now.isoformat(),
                    })
                case_repo._cases[cid]["relationship_count"] = len(created_ent_ids) - 1

        # Seed cross-case alert audit event
        ledger_service.local_store.append({
            "event_id": "ev-alert-demo-linkage-1",
            "record_id": "alert-linkage-lucknow-kanpur",
            "case_id": "DEMO-FIR-001",
            "actor": "system:cross_case_monitor",
            "action": "ALERT_GENERATED",
            "resource_type": "ALERT",
            "payload": {
                "alert_type": "CROSS_CASE_SYNDICATE_OVERLAP",
                "severity": "CRITICAL",
                "matched_cases": ["DEMO-FIR-001", "DEMO-FIR-002"],
                "overlap_entities": ["9000990189", "UP 32 AB 2618", "demohub26189@upi"],
            },
            "timestamp": now.isoformat(),
        })

        # 2. Load the 1,000 Synthetic Cases from data/synthetic/fir/fir_cases.json
        fir_json_path = ROOT / "data" / "synthetic" / "fir" / "fir_cases.json"
        if fir_json_path.exists():
            try:
                with open(fir_json_path, "r", encoding="utf-8") as f:
                    cases_data = json.load(f)

                for s_idx, item in enumerate(cases_data):
                    cid = item["case_id"]
                    num = int(cid.split("-")[-1]) if "-" in cid else 1
                    status = CaseStatus.IN_PROGRESS if num % 4 == 0 else CaseStatus.OPEN
                    priority = CasePriority.CRITICAL if num % 11 == 0 else (CasePriority.HIGH if num % 5 == 0 else CasePriority.MEDIUM)
                    location = item.get("location", "Unknown Location")
                    date = item.get("date", "2026-01-01")

                    case_repo._cases[cid] = {
                        "id": cid,
                        "case_number": cid,
                        "title": f"Investigation {cid} - {location}",
                        "description": item.get("complaint", ""),
                        "status": status,
                        "priority": priority,
                        "owner_id": admin_id,
                        "assigned_investigator_ids": assigned,
                        "tags": ["FIR", location, "SYNTHETIC"],
                        "document_count": 1,
                        "entity_count": 0,
                        "relationship_count": 0,
                        "created_at": now,
                        "updated_at": now,
                    }

                    if s_idx < 25:
                        ledger_service.local_store.append({
                            "event_id": f"ev-case-{cid}",
                            "record_id": cid,
                            "case_id": cid,
                            "actor": admin_id,
                            "action": "CASE_CREATED",
                            "resource_type": "CASE",
                            "payload": {"case_number": cid, "location": location, "priority": str(priority.value)},
                            "timestamp": now.isoformat(),
                        })

                    ent_ids = []
                    # Persons
                    persons = [p.strip() for p in item.get("persons", "").split("|") if p.strip()]
                    for p_idx, person in enumerate(persons):
                        eid = f"ent-{cid}-p{p_idx+1}"
                        entity_repo._entities[eid] = {
                            "id": eid,
                            "case_id": cid,
                            "name": person,
                            "entity_type": EntityType.PERSON,
                            "description": f"Suspect/associate identified in {cid}",
                            "properties": {"role": "SUSPECT" if p_idx == 0 else "ASSOCIATE"},
                            "confidence_score": 0.95,
                            "review_status": "CONFIRMED" if p_idx == 0 else "PENDING",
                            "created_at": now,
                            "updated_at": now,
                        }
                        ent_ids.append(eid)

                    # Phone
                    if item.get("phone"):
                        eid = f"ent-{cid}-phone"
                        entity_repo._entities[eid] = {
                            "id": eid,
                            "case_id": cid,
                            "name": item["phone"],
                            "entity_type": EntityType.PHONE_NUMBER,
                            "description": f"Phone extracted from {cid}",
                            "properties": {},
                            "confidence_score": 0.98,
                            "review_status": "CONFIRMED",
                            "created_at": now,
                            "updated_at": now,
                        }
                        ent_ids.append(eid)

                    # Vehicle
                    if item.get("vehicle"):
                        eid = f"ent-{cid}-vehicle"
                        entity_repo._entities[eid] = {
                            "id": eid,
                            "case_id": cid,
                            "name": item["vehicle"],
                            "entity_type": EntityType.VEHICLE,
                            "description": f"Vehicle observed in {cid}",
                            "properties": {},
                            "confidence_score": 0.92,
                            "review_status": "CONFIRMED",
                            "created_at": now,
                            "updated_at": now,
                        }
                        ent_ids.append(eid)

                    # UPI ID
                    if item.get("upi_id"):
                        eid = f"ent-{cid}-upi"
                        entity_repo._entities[eid] = {
                            "id": eid,
                            "case_id": cid,
                            "name": item["upi_id"],
                            "entity_type": EntityType.UPI_ID,
                            "description": f"Payment handle identified in {cid}",
                            "properties": {},
                            "confidence_score": 0.99,
                            "review_status": "CONFIRMED",
                            "created_at": now,
                            "updated_at": now,
                        }
                        ent_ids.append(eid)

                    # Location
                    if location:
                        eid = f"ent-{cid}-loc"
                        entity_repo._entities[eid] = {
                            "id": eid,
                            "case_id": cid,
                            "name": location,
                            "entity_type": EntityType.LOCATION,
                            "description": f"Incident location for {cid}",
                            "properties": {},
                            "confidence_score": 0.90,
                            "review_status": "CONFIRMED",
                            "created_at": now,
                            "updated_at": now,
                        }
                        ent_ids.append(eid)

                    case_repo._cases[cid]["entity_count"] = len(ent_ids)

                    # Create inter-entity edges
                    if ent_ids:
                        primary_ent = ent_ids[0]
                        for other_ent in ent_ids[1:]:
                            rid = f"rel-{cid}-{primary_ent}-{other_ent}"
                            relationship_repo._relationships[rid] = {
                                "id": rid,
                                "case_id": cid,
                                "source_entity_id": primary_ent,
                                "target_entity_id": other_ent,
                                "relationship_type": RelationshipType.ASSOCIATED_WITH,
                                "description": f"Evidence relationship in {cid}",
                                "properties": {},
                                "confidence_score": 0.90,
                                "created_at": now,
                                "updated_at": now,
                            }
                        case_repo._cases[cid]["relationship_count"] = max(0, len(ent_ids) - 1)

                    if s_idx < 25:
                        for eid in ent_ids[:3]:
                            ent = entity_repo._entities.get(eid)
                            if ent:
                                ent_type_val = ent["entity_type"].value if hasattr(ent["entity_type"], "value") else str(ent["entity_type"])
                                ledger_service.local_store.append({
                                    "event_id": f"ev-{eid}",
                                    "record_id": eid,
                                    "case_id": cid,
                                    "actor": "system:ai_extractor",
                                    "action": "ENTITY_EXTRACTED",
                                    "resource_type": "ENTITY",
                                    "payload": {"name": ent["name"], "entity_type": ent_type_val, "confidence": ent["confidence_score"]},
                                    "timestamp": now.isoformat(),
                                })
                        if len(ent_ids) >= 2:
                            rid = f"rel-{cid}-{ent_ids[0]}-{ent_ids[1]}"
                            ledger_service.local_store.append({
                                "event_id": f"ev-{rid}",
                                "record_id": rid,
                                "case_id": cid,
                                "actor": "system:linkage_engine",
                                "action": "RELATIONSHIP_CREATED",
                                "resource_type": "RELATIONSHIP",
                                "payload": {"source": ent_ids[0], "target": ent_ids[1], "type": "ASSOCIATED_WITH"},
                                "timestamp": now.isoformat(),
                            })

                logger.info("Loaded %d synthetic FIR cases into in-memory store", len(cases_data))
            except Exception as exc:
                logger.warning("Failed to load synthetic cases: %s", exc)

        # 3. Load Transactions Data for Dashboard Metrics & Timeline
        txn_path = ROOT / "data" / "synthetic" / "transactions" / "transactions.csv"
        if txn_path.exists():
            try:
                daily_amounts = defaultdict(float)
                daily_counts = defaultdict(int)
                total_flow = 0.0

                with open(txn_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        amt = float(row.get("amount", 0.0))
                        total_flow += amt
                        ts = row.get("timestamp", "")
                        day = ts[:10] if len(ts) >= 10 else "2026-01-01"
                        daily_amounts[day] += amt
                        daily_counts[day] += 1

                self.total_money_flow = total_flow
                sorted_days = sorted(daily_amounts.keys())[-30:]
                self.transaction_timeline = [
                    {"date": day, "amount": round(daily_amounts[day], 2), "count": daily_counts[day]}
                    for day in sorted_days
                ]
                logger.info("Loaded transaction totals: %f across %d timeline days", total_flow, len(self.transaction_timeline))
            except Exception as exc:
                logger.warning("Failed to parse transactions: %s", exc)

        self.loaded = True

synthetic_loader = SyntheticDataLoader()

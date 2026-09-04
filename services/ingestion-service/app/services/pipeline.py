
import httpx
import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

EXTRACTION_URL = os.getenv("EXTRACTION_SERVICE_URL", "http://extraction:8001") + "/api/v1/extract"
CASE_API_URL = os.getenv("API_SERVICE_URL", "http://api:8000") + "/api/v1"
SECRET_KEY = os.getenv("SECRET_KEY", "CRIMELENS_AI_SECRET_KEY_SUPER_SECURE_STUDENT_SIH_TOKEN_2026")
ALGORITHM = "HS256"

def get_system_token():
    expire = datetime.now(timezone.utc) + timedelta(minutes=60)
    to_encode = {
        "exp": expire,
        "sub": "user-admin-001",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

ENTITY_TYPE_MAPPING = {
    "PERSON": "PERSON",
    "PHONE": "PHONE_NUMBER",
    "VEHICLE": "VEHICLE",
    "UPI_ID": "BANK_ACCOUNT",
    "LOCATION": "LOCATION",
    "ORG": "ORGANIZATION"
}

class FIRPayload(BaseModel):
    case_id: str
    fir_id: str
    case_number: str
    title: str
    description: str
    fir_text: str
    district: str
    station: str
    filing_date: str

class CDRPayload(BaseModel):
    cdr_id: str
    case_id: str
    caller_phone: str
    receiver_phone: str
    timestamp: str
    duration_seconds: int
    location: Optional[str] = None
    cell_tower: Optional[str] = None

class TransactionPayload(BaseModel):
    transaction_id: str
    case_id: str
    timestamp: str
    sender_upi: str
    receiver_upi: str
    amount: float
    transaction_type: str
    description: Optional[str] = None

async def _get_real_case_id(client: httpx.AsyncClient, case_number: str, headers: dict) -> str:
    search_res = await client.get(f"{CASE_API_URL}/cases?search={case_number}", headers=headers)
    search_res.raise_for_status()
    existing_cases = search_res.json().get("items", [])
    
    for c in existing_cases:
        if c.get("case_number") == case_number:
            return c.get("id")
    raise ValueError(f"Case {case_number} not found")

async def _ensure_entity(client: httpx.AsyncClient, real_case_id: str, name: str, entity_type: str, headers: dict) -> str:
    exist_res = await client.get(f"{CASE_API_URL}/cases/{real_case_id}/entities", headers=headers)
    exist_res.raise_for_status()
    existing_items = exist_res.json().get("items", [])
    
    for e in existing_items:
        if e.get("name", "").lower() == name.lower() and e.get("entity_type") == entity_type:
            return e.get("id")
            
    ent_res = await client.post(f"{CASE_API_URL}/cases/{real_case_id}/entities", json={
        "name": name,
        "entity_type": entity_type,
        "description": "Implicitly created by ingestion",
        "confidence_score": 1.0
    }, headers=headers)
    ent_res.raise_for_status()
    return ent_res.json()["id"]

async def process_fir(payload: FIRPayload):
    if not payload.fir_text or not payload.fir_text.strip():
        raise ValueError("fir_text cannot be empty")

    token = get_system_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        ext_res = await client.post(EXTRACTION_URL, json={
            "text": payload.fir_text,
            "source_field": "fir_text"
        })
        ext_res.raise_for_status()
        extracted_entities = ext_res.json().get("entities", [])

        seen = set()
        normalized_entities = []
        for ent in extracted_entities:
            raw_type = ent["entity_type"]
            raw_value = ent["value"]
            
            if raw_type not in ENTITY_TYPE_MAPPING:
                continue
                
            mapped_type = ENTITY_TYPE_MAPPING[raw_type]
            norm_value = raw_value.strip()
            dedup_key = norm_value.lower()
                
            if dedup_key not in seen:
                seen.add(dedup_key)
                ent["entity_type"] = mapped_type
                ent["value"] = norm_value
                normalized_entities.append(ent)
                
        search_res = await client.get(f"{CASE_API_URL}/cases?search={payload.case_number}", headers=headers)
        search_res.raise_for_status()
        existing_cases = search_res.json().get("items", [])
        
        real_case_id = None
        for c in existing_cases:
            if c.get("case_number") == payload.case_number:
                real_case_id = c.get("id")
                break
                
        if not real_case_id:
            case_res = await client.post(f"{CASE_API_URL}/cases", json={
                "title": payload.title,
                "description": payload.description,
                "case_number": payload.case_number,
                "priority": "MEDIUM",
                "tags": ["FIR", payload.district, payload.case_id]
            }, headers=headers)
            case_res.raise_for_status()
            real_case_id = case_res.json()["id"]
        
        exist_res = await client.get(f"{CASE_API_URL}/cases/{real_case_id}/entities", headers=headers)
        exist_res.raise_for_status()
        existing_items = exist_res.json().get("items", [])
        
        existing_set = set()
        for e in existing_items:
            v = e.get("name", "").strip()
            existing_set.add(v.lower())

        saved_entities = []
        for ent in normalized_entities:
            mapped_type = ent["entity_type"]
            norm_value = ent["value"]
            
            check_key = norm_value.lower()
                
            if check_key not in existing_set:
                ent_res = await client.post(f"{CASE_API_URL}/cases/{real_case_id}/entities", json={
                    "name": norm_value,
                    "entity_type": mapped_type,
                    "description": "Extracted from FIR",
                    "properties": {
                        "confidence": ent["confidence"],
                        "start_offset": ent["start_offset"],
                        "end_offset": ent["end_offset"]
                    },
                    "confidence_score": ent["confidence"]
                }, headers=headers)
                
                ent_res.raise_for_status()
                saved_entities.append(ent_res.json())
                
    return {
        "case_id": payload.case_id,
        "real_case_id": real_case_id,
        "extracted_count": len(extracted_entities),
        "normalized_count": len(normalized_entities),
        "saved_count": len(saved_entities),
        "entities": saved_entities
    }

async def process_cdr(payload: CDRPayload):
    token = get_system_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        real_case_id = await _get_real_case_id(client, payload.case_id, headers)
        
        caller_id = await _ensure_entity(client, real_case_id, payload.caller_phone, "PHONE_NUMBER", headers)
        receiver_id = await _ensure_entity(client, real_case_id, payload.receiver_phone, "PHONE_NUMBER", headers)
        
        rels_res = await client.get(f"{CASE_API_URL}/cases/{real_case_id}/relationships?limit=200", headers=headers)
        rels_res.raise_for_status()
        rels = rels_res.json().get("items", [])
        
        for r in rels:
            if r.get("properties", {}).get("cdr_id") == payload.cdr_id:
                return {"status": "skipped", "message": "CDR already processed", "cdr_id": payload.cdr_id}
                
        rel_res = await client.post(f"{CASE_API_URL}/cases/{real_case_id}/relationships", json={
            "source_entity_id": caller_id,
            "target_entity_id": receiver_id,
            "relationship_type": "COMMUNICATED_WITH",
            "description": f"Call duration: {payload.duration_seconds}s",
            "properties": {
                "cdr_id": payload.cdr_id,
                "timestamp": payload.timestamp,
                "duration_seconds": payload.duration_seconds,
                "location": payload.location,
                "cell_tower": payload.cell_tower
            },
            "confidence_score": 1.0
        }, headers=headers)
        rel_res.raise_for_status()
        
    return {"status": "created", "cdr_id": payload.cdr_id, "relationship_id": rel_res.json()["id"]}

async def process_transaction(payload: TransactionPayload):
    token = get_system_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        real_case_id = await _get_real_case_id(client, payload.case_id, headers)
        
        sender_id = await _ensure_entity(client, real_case_id, payload.sender_upi, "BANK_ACCOUNT", headers)
        receiver_id = await _ensure_entity(client, real_case_id, payload.receiver_upi, "BANK_ACCOUNT", headers)
        
        rels_res = await client.get(f"{CASE_API_URL}/cases/{real_case_id}/relationships?limit=200", headers=headers)
        rels_res.raise_for_status()
        rels = rels_res.json().get("items", [])
        
        for r in rels:
            if r.get("properties", {}).get("transaction_id") == payload.transaction_id:
                return {"status": "skipped", "message": "Transaction already processed", "transaction_id": payload.transaction_id}
                
        rel_res = await client.post(f"{CASE_API_URL}/cases/{real_case_id}/relationships", json={
            "source_entity_id": sender_id,
            "target_entity_id": receiver_id,
            "relationship_type": "TRANSFERRED_FUNDS",
            "description": payload.description or f"Transaction of {payload.amount}",
            "properties": {
                "transaction_id": payload.transaction_id,
                "timestamp": payload.timestamp,
                "amount": payload.amount,
                "transaction_type": payload.transaction_type
            },
            "confidence_score": 1.0
        }, headers=headers)
        rel_res.raise_for_status()
        
    return {"status": "created", "transaction_id": payload.transaction_id, "relationship_id": rel_res.json()["id"]}


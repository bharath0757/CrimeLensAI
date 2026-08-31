import httpx
import os
import jwt
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
from pydantic import BaseModel

EXTRACTION_URL = os.getenv("EXTRACTION_URL", "http://localhost:8001/api/v1/extract")
CASE_API_URL = os.getenv("CASE_API_URL", "http://localhost:8000/api/v1")
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

async def process_fir(payload: FIRPayload):
    if not payload.fir_text or not payload.fir_text.strip():
        raise ValueError("fir_text cannot be empty")

    token = get_system_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Extract entities
        ext_res = await client.post(EXTRACTION_URL, json={
            "text": payload.fir_text,
            "source_field": "fir_text"
        })
        ext_res.raise_for_status()
        extracted_entities = ext_res.json().get("entities", [])

        # 2. Normalize and Deduplicate
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
                
        # 3. Ensure Case exists (Idempotent)
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
                "tags": ["FIR", payload.district]
            }, headers=headers)
            case_res.raise_for_status()
            real_case_id = case_res.json()["id"]
        
        # 4. Fetch existing entities to prevent global duplicates for this case
        exist_res = await client.get(f"{CASE_API_URL}/cases/{real_case_id}/entities", headers=headers)
        exist_res.raise_for_status()
        existing_items = exist_res.json().get("items", [])
        
        existing_set = set()
        for e in existing_items:
            v = e.get("name", "").strip()
            existing_set.add(v.lower())

        # 5. Persist novel entities
        saved_entities = []
        for ent in normalized_entities:
            mapped_type = ent["entity_type"]
            norm_value = ent["value"]
            
            check_key = norm_value.lower()
                
            if check_key not in existing_set:
                ent_res = await client.post(f"{CASE_API_URL}/cases/{real_case_id}/entities", json={
                    "name": norm_value,
                    "entity_type": mapped_type,
                    "description": f"Extracted from FIR",
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

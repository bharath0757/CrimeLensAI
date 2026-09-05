"""Legacy JSON adapters retain the officer identity; never mint system/admin JWTs."""

import os
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field


class FIRPayload(BaseModel):
    case_id: str
    fir_id: str
    case_number: str
    title: str
    description: str
    fir_text: str = Field(min_length=1, max_length=500_000)
    district: str
    station: str
    filing_date: str


class CDRPayload(BaseModel):
    cdr_id: str
    case_id: str
    caller_phone: str
    receiver_phone: str
    timestamp: str
    duration_seconds: int = Field(ge=0)
    cell_tower: str
    imei: str


class TransactionPayload(BaseModel):
    transaction_id: str
    case_id: str
    timestamp: str
    sender_upi: str
    receiver_upi: str
    amount: str | float
    transaction_type: str = "UPI"
    description: str | None = None


async def request(client, method, path, **kwargs):
    try:
        response = await client.request(method, path, **kwargs)
        if response.status_code in {401, 403, 404, 409, 413, 422}:
            raise HTTPException(response.status_code, response.json().get("detail", "Case API rejected ingestion"))
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Case API ingestion unavailable") from exc


def client_for(authorization):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "An officer Bearer token is required")
    configured = os.getenv("API_SERVICE_URL", "http://api:8000").strip().rstrip("/")
    base = (configured if "://" in configured else f"http://{configured}") + "/api/v1/"
    return httpx.AsyncClient(base_url=base, headers={"Authorization": authorization}, timeout=120)


async def find_case(client, identifier):
    # The gateway performs case-access checks on both lookup and final write.
    try:
        return await request(client, "GET", f"cases/{quote(identifier, safe='')}")
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    page = await request(client, "GET", "cases", params={"search": identifier, "limit": 100})
    return next((case for case in page["items"] if case["case_number"] == identifier), None)


async def process_fir(payload: FIRPayload, authorization: str):
    async with client_for(authorization) as client:
        await request(client, "GET", "auth/me")
        case = await find_case(client, payload.case_number)
        if case is None:
            case = await request(client, "POST", "cases", json={"case_number": payload.case_number, "title": payload.title, "description": payload.description,
                                "tags": ["FIR", payload.district, payload.station, payload.filing_date, payload.fir_id, payload.case_id]})
        document = await request(client, "POST", f"cases/{case['id']}/documents", files={"file": ("fir.txt", payload.fir_text.encode("utf-8"), "text/plain")})
        processed = await request(client, "POST", f"documents/{document['id']}/process")
        return {"case_id": payload.case_id, "real_case_id": case["id"], "document_id": document["id"], "processing": processed}


async def structured(payload, authorization, kind, row):
    async with client_for(authorization) as client:
        await request(client, "GET", "auth/me")
        case = await find_case(client, payload.case_id)
        if case is None:
            raise HTTPException(404, "Case not found")
        return await request(client, "POST", f"cases/{case['id']}/ingestion/records", json={"kind": kind, "records": [row]})


async def process_cdr(payload: CDRPayload, authorization: str):
    row = {"cdr_id": payload.cdr_id, "caller": payload.caller_phone, "receiver": payload.receiver_phone, "timestamp": payload.timestamp,
           "duration": payload.duration_seconds, "tower": payload.cell_tower, "imei": payload.imei}
    return await structured(payload, authorization, "cdr", row)


async def process_transaction(payload: TransactionPayload, authorization: str):
    row = {"transaction_id": payload.transaction_id, "sender": payload.sender_upi, "receiver": payload.receiver_upi, "upi": payload.receiver_upi, "amount": payload.amount, "timestamp": payload.timestamp}
    row["transaction_type"] = payload.transaction_type
    if payload.description is not None:
        row["description"] = payload.description
    return await structured(payload, authorization, "transactions", row)

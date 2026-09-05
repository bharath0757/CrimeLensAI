"""Strict, all-or-nothing CSV validation without database or credential access."""

import csv
import hashlib
import io
import json
import re

from fastapi import HTTPException
from pydantic import ValidationError

from app.models import EvidenceRow, ValidationRequest, ValidationResult

ALIASES = {"caller_phone": "caller", "receiver_phone": "receiver", "duration_seconds": "duration", "cell_tower": "tower", "upi_id": "upi"}
REQUIRED = {
    "cdr": {"caller", "receiver", "timestamp", "duration", "tower", "imei"},
    "transactions": {"sender", "receiver", "amount", "upi", "timestamp", "transaction_id"},
}


def phone(value: str) -> str:
    if not re.fullmatch(r"\+?[0-9 ()-]{8,24}", value):
        raise ValueError("Phone must contain digits and optional +, spaces, brackets or hyphens")
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if not 8 <= len(digits) <= 15:
        raise ValueError("Phone must contain 8 to 15 digits")
    return digits


def headers(keys):
    normalized = [ALIASES.get(str(key).strip().lower(), str(key).strip().lower()) for key in keys]
    if len(set(normalized)) != len(normalized):
        raise HTTPException(422, "Duplicate or ambiguous CSV headers")
    return normalized


def validate(request: ValidationRequest) -> ValidationResult:
    if (request.csv_text is None) == (request.records is None):
        raise HTTPException(422, "Provide exactly one of csv_text or records")
    incoming = []
    if request.csv_text is not None:
        if "\x00" in request.csv_text:
            raise HTTPException(422, "CSV must not contain NUL characters")
        reader = csv.reader(io.StringIO(request.csv_text.lstrip("\ufeff")), strict=True)
        try:
            names = headers(next(reader))
            while True:
                line = reader.line_num + 1
                values = next(reader, None)
                if values is None:
                    break
                if not values:
                    continue
                if len(values) != len(names):
                    raise HTTPException(422, f"CSV row {line}: wrong number of columns")
                incoming.append((line, dict(zip(names, values, strict=True))))
                if len(incoming) > 20_000:
                    raise HTTPException(413, "At most 20,000 records per upload")
        except (csv.Error, StopIteration) as exc:
            raise HTTPException(422, "CSV is empty or malformed") from exc
    else:
        for index, record in enumerate(request.records or [], start=1):
            incoming.append((index, dict(zip(headers(record.keys()), record.values(), strict=True))))
    if not incoming:
        raise HTTPException(422, "At least one evidence record is required")
    records, seen, duplicates, derived = [], {}, 0, False
    for line, raw in incoming:
        try:
            if any(value is None or isinstance(value, dict | list | bool) for value in raw.values()):
                raise ValueError("Evidence fields must be non-null strings or numbers")
            row = {key: str(value).strip() for key, value in raw.items()}
            missing = REQUIRED[request.kind] - row.keys()
            optional = {"case_id", "cdr_id"} if request.kind == "cdr" else {"case_id", "transaction_type", "description"}
            allowed = REQUIRED[request.kind] | optional
            if missing or row.keys() - allowed:
                raise ValueError(f"Required headers: {', '.join(sorted(REQUIRED[request.kind]))}; optional: {', '.join(sorted(optional))}")
            if row.get("case_id") and row["case_id"] not in {request.case_id, request.case_number}:
                raise ValueError("Record belongs to a different case; upload one case at a time")
            if request.kind == "cdr":
                source, target = phone(row["caller"]), phone(row["receiver"])
                source_type = target_type = "PHONE_NUMBER"
                if not re.fullmatch(r"[0-9]{15}", row["imei"]):
                    raise ValueError("IMEI must contain exactly 15 digits")
                values = {"duration": row["duration"], "tower": row["tower"], "imei": row["imei"]}
                identifier = row.get("cdr_id", "")
            else:
                source, target = row["sender"], row["receiver"]
                def payment_type(value):
                    if re.fullmatch(r"[0-9]{6,34}", value):
                        return "BANK_ACCOUNT"
                    if re.fullmatch(r"[A-Za-z0-9._-]{2,128}@[A-Za-z][A-Za-z0-9.-]{1,63}", value):
                        return "UPI_ID"
                    raise ValueError("Sender and receiver must be bank account numbers or valid UPI handles")
                source_type, target_type = payment_type(source), payment_type(target)
                source, target = source.lower(), target.lower()
                if not re.fullmatch(r"[A-Za-z0-9._-]{2,128}@[A-Za-z][A-Za-z0-9.-]{1,63}", row["upi"]):
                    raise ValueError("Invalid UPI identifier")
                values = {"amount": row["amount"], "upi": row["upi"].lower()}
                values.update({key: row[key] for key in ("transaction_type", "description") if row.get(key)})
                identifier = row["transaction_id"]
                if not identifier:
                    raise ValueError("transaction_id must not be blank")
            record = EvidenceRow(record_id=identifier or "derived", row_number=line, source=source, target=target,
                                 source_type=source_type, target_type=target_type, timestamp=row["timestamp"], **values)
            content = record.model_dump(mode="json", exclude={"row_number", "record_id"})
            fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
            if not identifier:
                derived = True
                record.record_id = "derived-cdr-" + fingerprint
            if record.record_id in seen:
                if seen[record.record_id] != content:
                    raise ValueError("Same evidence ID has conflicting contents")
                duplicates += 1
                continue
            seen[record.record_id] = content
            records.append(record)
        except (ValueError, ValidationError) as exc:
            message = str(exc) if not isinstance(exc, ValidationError) else "; ".join(f"{error['loc'][0]}: {error['msg']}" for error in exc.errors())
            raise HTTPException(422, f"Row {line}: {message}") from exc
    warnings = ["Missing CDR IDs were derived from normalized contents; identical rows are treated as duplicate evidence."] if derived else []
    return ValidationResult(kind=request.kind, records=records, input_rows=len(incoming), duplicate_rows=duplicates, warnings=warnings)

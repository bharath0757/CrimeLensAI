"""Canonical identity values shared by case persistence and graph adaptation."""

import re


def normalized_entity_value(entity_type: str, value: str) -> str:
    if entity_type in {"PHONE", "PHONE_NUMBER"}:
        digits = re.sub(r"\D", "", value)
        if (len(digits) == 12 and digits.startswith("91")) or (len(digits) == 11 and digits.startswith("0")):
            return digits[-10:]
        return digits
    if entity_type in {"AADHAAR", "BANK_ACCOUNT"}:
        return re.sub(r"\D", "", value)
    if entity_type in {"PAN", "PASSPORT", "VEHICLE"}:
        return re.sub(r"[^A-Za-z0-9]", "", value).upper()
    return " ".join(value.split()).casefold()

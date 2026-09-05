"""
CrimeLensAI — Entity Value Normalizers
========================================
Type-specific normalization functions.

Each normalizer takes the raw extracted ``value`` and returns a
canonical ``normalized_value``.  The original value is always
preserved separately — normalization never destroys provenance.
"""

from __future__ import annotations

import re


def normalize_person(value: str) -> str:
    """Collapse whitespace and lowercase.

    ``" RAJESH  KUMAR "`` → ``"rajesh kumar"``
    """
    return " ".join(value.split()).lower()


def normalize_phone(value: str) -> str:
    """Strip non-digits, ensure ``+91`` prefix.

    ``"+91 98765 43210"`` → ``"+919876543210"``
    ``"09876543210"``     → ``"+919876543210"``
    ``"9876543210"``      → ``"+919876543210"``
    """
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        return f"+{digits}"
    if len(digits) == 11 and digits.startswith("0"):
        return f"+91{digits[1:]}"
    if len(digits) == 10:
        return f"+91{digits}"
    # Fallback: return cleaned digits
    return digits


def normalize_vehicle(value: str) -> str:
    """Strip spaces/dashes and uppercase.

    ``"AP 39 AB 1234"`` → ``"AP39AB1234"``
    ``"ka-01-mg-1234"`` → ``"KA01MG1234"``
    """
    return re.sub(r"[\s\-]", "", value).upper()


def normalize_upi(value: str) -> str:
    """Lowercase and strip whitespace.

    ``"RAJESH@OKSBI"`` → ``"rajesh@oksbi"``
    """
    return value.strip().lower()


def normalize_location(value: str) -> str:
    """Strip whitespace and title-case.

    ``"  hyderabad  "`` → ``"Hyderabad"``
    """
    return " ".join(value.split()).title()


def normalize_org(value: str) -> str:
    """Collapse whitespace and lowercase.

    ``"  State  Bank of India "`` → ``"state bank of india"``
    """
    return " ".join(value.split()).lower()


def normalize_date(value: str) -> str:
    """Light normalization: strip and lowercase.

    ``" 15th January 2024 "`` → ``"15th january 2024"``
    """
    return " ".join(value.split()).lower()


def normalize_compact_identifier(value: str) -> str:
    """Normalize identity numbers while preserving alphanumeric meaning."""
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def normalize_email(value: str) -> str:
    return value.strip().lower()


def normalize_legal_section(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


# ------------------------------------------------------------------
# Dispatcher
# ------------------------------------------------------------------

_NORMALIZERS: dict[str, callable] = {
    "PERSON": normalize_person,
    "PHONE": normalize_phone,
    "VEHICLE": normalize_vehicle,
    "UPI_ID": normalize_upi,
    "LOCATION": normalize_location,
    "ORG": normalize_org,
    "DATE": normalize_date,
    "AADHAAR": normalize_digits,
    "PAN": normalize_compact_identifier,
    "PASSPORT": normalize_compact_identifier,
    "BANK_ACCOUNT": normalize_digits,
    "EMAIL": normalize_email,
    "IPC_SECTION": normalize_legal_section,
}


def normalize(entity_type: str, value: str) -> str:
    """Return the normalized value for the given entity type.

    Falls back to stripped lowercase if the type is unknown.
    """
    fn = _NORMALIZERS.get(entity_type)
    if fn is None:
        return value.strip().lower()
    return fn(value)

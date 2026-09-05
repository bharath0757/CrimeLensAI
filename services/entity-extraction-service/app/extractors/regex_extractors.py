"""
CrimeLensAI — Regex-Based Entity Extractors
=============================================
Deterministic regex extractors for Indian-specific entity types
that spaCy NER does not handle reliably:

* Indian mobile phone numbers
* Indian vehicle registration plates
* UPI IDs (user@bank)

Each extractor returns a list of raw match dicts with character
offsets into the **original** text.
"""

from __future__ import annotations

import re
from typing import TypedDict

from app.core.config import settings


class RawMatch(TypedDict):
    """Intermediate match result from a regex extractor."""
    entity_type: str
    value: str
    start_offset: int
    end_offset: int
    confidence: float


# ==================================================================
# Phone Number Patterns (Indian)
# ==================================================================
# Matches:
#   +91 98765 43210, +91-9876543210, 09876543210, 9876543210
#   +91 (987) 654-3210  (with optional grouping)
# Does NOT match partial digit sequences < 10 digits.
# ==================================================================

_PHONE_PATTERN = re.compile(
    r"""
    (?<!\d)                          # no digit before
    (?:\+91[\s\-]?)?                 # optional +91 prefix
    0?                               # optional trunk 0
    [6-9]                            # Indian mobile starts with 6-9
    (?:[\s\-]?\d){9}                 # remaining 9 digits (with optional separators)
    (?!\d)                           # no digit after
    """,
    re.VERBOSE,
)

# After stripping non-digits the number must be 10, 11 (0-prefix), or 12 (+91) digits.
_PHONE_DIGIT_COUNTS = {10, 11, 12}


def extract_phones(text: str) -> list[RawMatch]:
    """Extract Indian phone numbers from *text*."""
    matches: list[RawMatch] = []
    for m in _PHONE_PATTERN.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        # Accept 10-digit or 12-digit (+91…) numbers
        if len(digits) not in _PHONE_DIGIT_COUNTS:
            continue
        # Reject numbers that are all the same digit (e.g. 0000000000)
        if len(set(digits[-10:])) == 1:
            continue
        matches.append(
            RawMatch(
                entity_type="PHONE",
                value=m.group(),
                start_offset=m.start(),
                end_offset=m.end(),
                confidence=settings.CONFIDENCE_REGEX,
            )
        )
    return matches


# ==================================================================
# Vehicle Registration Patterns (Indian)
# ==================================================================
# Formats:  AP 39 AB 1234, KA01MG1234, MH-12-AB-1234
# State code (2 letters) + district (1-2 digits) + series (0-3 letters) + number (1-4 digits)
# ==================================================================

_VEHICLE_PATTERN = re.compile(
    r"""
    (?<![A-Za-z0-9])                 # word boundary
    ([A-Z]{2})                       # state code
    [\s\-]?
    (\d{1,2})                        # district code
    [\s\-]?
    ([A-Z]{0,3})                     # series letters (may be absent)
    [\s\-]?
    (\d{1,4})                        # registration number
    (?![A-Za-z0-9])                  # word boundary
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Known Indian state codes (2-letter RTO prefixes)
_INDIAN_STATE_CODES = {
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "DD", "DL", "GA",
    "GJ", "HP", "HR", "JH", "JK", "KA", "KL", "LA", "LD", "MH",
    "ML", "MN", "MP", "MZ", "NL", "OD", "PB", "PY", "RJ", "SK",
    "TN", "TR", "TS", "UK", "UP", "WB",
}


def extract_vehicles(text: str) -> list[RawMatch]:
    """Extract Indian vehicle registration numbers from *text*."""
    matches: list[RawMatch] = []
    for m in _VEHICLE_PATTERN.finditer(text):
        state = m.group(1).upper()
        if state not in _INDIAN_STATE_CODES:
            continue
        # Must have at least 4 chars total (state+district+number)
        raw = m.group()
        if len(re.sub(r"[\s\-]", "", raw)) < 6:
            continue
        matches.append(
            RawMatch(
                entity_type="VEHICLE",
                value=m.group(),
                start_offset=m.start(),
                end_offset=m.end(),
                confidence=settings.CONFIDENCE_REGEX,
            )
        )
    return matches


# ==================================================================
# UPI ID Patterns
# ==================================================================
# Format: username@bankhandle
# ==================================================================

_UPI_PATTERN = re.compile(
    r"""
    (?<!\S)                          # preceded by whitespace or start
    ([a-zA-Z0-9._\-]+)              # username
    @
    ([a-zA-Z]{2,})                   # bank handle (oksbi, ybl, paytm, etc.)
    (?=[\s.,;:!?)\]\}]|$)            # followed by whitespace, punctuation, or end
    """,
    re.VERBOSE,
)

# Common UPI bank handles to reduce false positives (e.g. email addresses)
_UPI_HANDLES = {
    "oksbi", "okhdfcbank", "okicici", "okaxis", "ybl", "ibl", "apl",
    "paytm", "upi", "axl", "sbi", "hdfcbank", "icici", "axisbank",
    "kotak", "indus", "boi", "pnb", "cnrb", "allbank", "unionbank",
    "idfcfirst", "fbl", "rbl", "kvb", "equitas", "dbs", "federal",
    "abfspay", "freecharge", "amazonpay", "gpay", "phonepe",
    "jupiteraxis", "slice", "cred",
}


def extract_upis(text: str) -> list[RawMatch]:
    """Extract UPI IDs from *text*."""
    matches: list[RawMatch] = []
    for m in _UPI_PATTERN.finditer(text):
        handle = m.group(2).lower()
        if handle not in _UPI_HANDLES:
            continue
        matches.append(
            RawMatch(
                entity_type="UPI_ID",
                value=m.group(),
                start_offset=m.start(),
                end_offset=m.end(),
                confidence=settings.CONFIDENCE_REGEX,
            )
        )
    return matches


# ==================================================================
# Identity, financial, contact, legal, and FIR-context patterns
# ==================================================================

_AADHAAR_PATTERN = re.compile(
    r"(?i:\baadhaa?r(?:\s+(?:number|no\.?))?\s*[:#-]?\s*)"
    r"(?P<value>[2-9]\d{3}[ -]?\d{4}[ -]?\d{4})(?!\d)"
)
_PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b", re.IGNORECASE)
_PASSPORT_PATTERN = re.compile(r"\b[A-Z][1-9]\d{6}\b", re.IGNORECASE)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_BANK_ACCOUNT_PATTERN = re.compile(
    r"(?i)\b(?:bank\s+)?(?:a/?c|account)(?:\s+(?:number|no\.?))?\s*[:#-]?\s*(\d{9,18})\b"
)
_IPC_PATTERN = re.compile(
    r"(?i)\b(?:(?:section|sec\.?)\s*)?(?P<section>\d{1,3}[A-Z]?)\s*"
    r"(?:of\s+the\s+)?(?P<code>IPC|BNS)\b|\b(?P<code_first>IPC|BNS)\s*"
    r"(?:section|sec\.?)?\s*(?P<section_after>\d{1,3}[A-Z]?)\b"
)
_DATE_PATTERN = re.compile(
    r"\b(?:\d{1,2}(?:st|nd|rd|th)?[\s/-]+"
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|\d{1,2})"
    r"[\s/-]+\d{2,4}|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)

_PERSON_CONTEXT_PATTERNS = [
    re.compile(r"(?i:\b(?:against|accused|suspect|witness|complainant|victim)\s+)"
               r"(?P<value>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})"),
    re.compile(r"(?i:\blinks?\s+(?:it\s+)?to\s+)"
               r"(?P<value>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3})"),
]
_LOCATION_CONTEXT_PATTERNS = [
    re.compile(r"(?i:\b(?:at|near|in|from)\s+)"
               r"(?P<value>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3})"
               r"(?=[.,;]|\s+(?:on|where|and|before|after)\b)"),
]
_ORG_CONTEXT_PATTERNS = [
    re.compile(r"(?i:\bfrom\s+)(?P<value>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,4})"
               r"(?=\s+(?:reported|filed|transferred|received)\b)"),
    re.compile(r"\b(?P<value>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,4}\s+"
               r"(?:Pvt\.?\s+Ltd\.?|Limited|Ltd\.?|Corp(?:oration)?|Enterprises|"
               r"Trading|Holdings|Bank|Foundation|Company|Services))\b"),
]


def _simple_matches(
    text: str,
    pattern: re.Pattern[str],
    entity_type: str,
    confidence: float,
    group: str | int = 0,
) -> list[RawMatch]:
    matches: list[RawMatch] = []
    for item in pattern.finditer(text):
        value = item.group(group)
        start, end = item.span(group)
        matches.append(
            RawMatch(
                entity_type=entity_type,
                value=value,
                start_offset=start,
                end_offset=end,
                confidence=confidence,
            )
        )
    return matches


def extract_extended_identifiers(text: str) -> list[RawMatch]:
    """Extract Indian identifiers and legal references with source offsets."""
    matches: list[RawMatch] = []
    matches.extend(_simple_matches(text, _AADHAAR_PATTERN, "AADHAAR", 0.97, "value"))
    matches.extend(_simple_matches(text, _PAN_PATTERN, "PAN", 0.98))
    matches.extend(_simple_matches(text, _PASSPORT_PATTERN, "PASSPORT", 0.96))
    matches.extend(_simple_matches(text, _EMAIL_PATTERN, "EMAIL", 0.98))
    matches.extend(_simple_matches(text, _BANK_ACCOUNT_PATTERN, "BANK_ACCOUNT", 0.94, 1))
    matches.extend(_simple_matches(text, _DATE_PATTERN, "DATE", 0.92))
    for item in _IPC_PATTERN.finditer(text):
        matches.append(
            RawMatch(
                entity_type="IPC_SECTION",
                value=item.group(),
                start_offset=item.start(),
                end_offset=item.end(),
                confidence=0.97,
            )
        )
    return matches


def extract_context_entities(text: str) -> list[RawMatch]:
    """Provide deterministic FIR fallbacks when a statistical NER model is absent."""
    matches: list[RawMatch] = []
    for pattern in _PERSON_CONTEXT_PATTERNS:
        matches.extend(_simple_matches(text, pattern, "PERSON", 0.75, "value"))
    for pattern in _LOCATION_CONTEXT_PATTERNS:
        matches.extend(_simple_matches(text, pattern, "LOCATION", 0.70, "value"))
    for pattern in _ORG_CONTEXT_PATTERNS:
        matches.extend(_simple_matches(text, pattern, "ORG", 0.75, "value"))
    return matches


# ==================================================================
# Public API
# ==================================================================

def run_all_regex(text: str) -> list[RawMatch]:
    """Run all regex extractors and return combined matches."""
    results: list[RawMatch] = []
    results.extend(extract_phones(text))
    results.extend(extract_vehicles(text))
    results.extend(extract_upis(text))
    results.extend(extract_extended_identifiers(text))
    results.extend(extract_context_entities(text))
    return results

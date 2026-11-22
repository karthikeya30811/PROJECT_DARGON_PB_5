"""Masks sensitive IDs (Aadhaar, PAN, bank-like numbers) and checks wording.

Patterns are applied in order (Aadhaar, PAN, bank-like). A span already
claimed by an earlier pattern is not reported again, so a 12-digit Aadhaar
is reported once, as "aadhaar".
"""

import re

AADHAAR_PATTERN = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")
PAN_PATTERN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
BANK_PATTERN = re.compile(r"\b\d{9,18}\b")

SENSITIVE_PATTERNS = [
    ("aadhaar", AADHAAR_PATTERN),
    ("pan", PAN_PATTERN),
    ("bank_account", BANK_PATTERN),
]

MASK_TOKEN = "[masked]"

FORBIDDEN_WORDS = ["guaranteed"]


def find_sensitive(text):
    """Return a list of {type, start, end} for each sensitive span, in order."""
    text = text or ""
    found = []
    taken = []
    for type_name, pattern in SENSITIVE_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < t_end and t_start < end for t_start, t_end in taken):
                continue
            taken.append((start, end))
            found.append({"type": type_name, "start": start, "end": end})
    found.sort(key=lambda item: item["start"])
    return found


def mask_sensitive(text):
    """Replace sensitive spans with MASK_TOKEN. Returns (masked_text, found_types)."""
    text = text or ""
    found = find_sensitive(text)
    if not found:
        return text, []
    parts = []
    position = 0
    types = []
    for item in found:
        parts.append(text[position:item["start"]])
        parts.append(MASK_TOKEN)
        position = item["end"]
        if item["type"] not in types:
            types.append(item["type"])
    parts.append(text[position:])
    return "".join(parts), types


def check_wording(strings):
    """Return a list of violation messages for forbidden words (case-insensitive)."""
    violations = []
    for value in strings:
        lowered = str(value).lower()
        for word in FORBIDDEN_WORDS:
            if word in lowered:
                violations.append(f"forbidden word '{word}' in: {value}")
    return violations

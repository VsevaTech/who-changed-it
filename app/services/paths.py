"""Raw and human-readable JSON paths."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Abbreviations that read better upper-cased in display paths.
ACRONYMS = {
    "id": "ID",
    "tid": "TID",
    "mid": "MID",
    "uuid": "UUID",
    "url": "URL",
    "uri": "URI",
    "api": "API",
    "iban": "IBAN",
    "bic": "BIC",
    "vat": "VAT",
    "trn": "TRN",
    "pos": "POS",
    "kyc": "KYC",
    "sms": "SMS",
    "ip": "IP",
    "3ds": "3DS",
    "erp": "ERP",
    "crm": "CRM",
    "psp": "PSP",
    "qr": "QR",
    "sku": "SKU",
}

# Well-known root sections mapped to change groups. Unknown roots use their own name.
KNOWN_GROUPS = {
    "company": "Company",
    "merchant": "Company",
    "organization": "Company",
    "payments": "Payments",
    "payment": "Payments",
    "payment_settings": "Payments",
    "acquiring": "Payments",
    "terminals": "Terminals",
    "terminal": "Terminals",
    "devices": "Terminals",
    "features": "Features",
    "feature_flags": "Features",
    "flags": "Features",
    "billing": "Billing",
    "invoicing": "Billing",
    "locations": "Locations",
    "stores": "Locations",
}
OTHER_GROUP = "Other"

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


@dataclass(frozen=True)
class Segment:
    """One step of a path: an object key, or an array element (by identity or index)."""

    key: str | None = None  # object key
    array: str | None = None  # parent array name (for display)
    identity: str | None = None  # "id=T2" for identity matches
    index: int | None = None  # positional fallback / value-matched scalars

    @property
    def is_element(self) -> bool:
        return self.key is None


def humanize_key(key: str) -> str:
    words = [w for w in re.split(r"[_\-\s]+", _CAMEL_RE.sub("_", key)) if w]
    if not words:
        return key
    out: list[str] = []
    for i, w in enumerate(words):
        low = w.lower()
        if low in ACRONYMS:
            out.append(ACRONYMS[low])
        elif i == 0:
            out.append(w[:1].upper() + w[1:].lower() if not w.isupper() else w.capitalize())
        else:
            out.append(low)
    return " ".join(out)


def singularize(word: str) -> str:
    low = word.lower()
    if low.endswith("ies") and len(low) > 3:
        return word[:-3] + "y"
    if low.endswith(("ss", "us", "is")):
        return word
    if low.endswith("es") and low[:-2].endswith(("sh", "ch", "x", "z")):
        return word[:-2]
    if low.endswith("s") and len(low) > 1:
        return word[:-1]
    return word


def raw_path(segments: list[Segment]) -> str:
    parts: list[str] = []
    for seg in segments:
        if seg.key is not None:
            if parts:
                parts.append(".")
            parts.append(
                seg.key if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", seg.key) else f'["{seg.key}"]'
            )
        elif seg.identity is not None:
            parts.append(f"[{seg.identity}]")
        else:
            parts.append(f"[{seg.index}]")
    return "".join(parts) or "$"


def display_path(segments: list[Segment]) -> str:
    """``terminals[id=T2].tid`` → ``Terminal T2 / TID``."""
    parts: list[str] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        nxt = segments[i + 1] if i + 1 < len(segments) else None
        if seg.key is not None and nxt is not None and nxt.is_element:
            label = humanize_key(singularize(seg.key))
            if nxt.identity is not None:
                value = nxt.identity.split("=", 1)[1]
                parts.append(f"{label} {value}")
            else:
                parts.append(f"{label} #{nxt.index}")
            i += 2
            continue
        if seg.key is not None:
            parts.append(humanize_key(seg.key))
        elif seg.identity is not None:
            parts.append(f"Item {seg.identity.split('=', 1)[1]}")
        else:
            parts.append(f"Item #{seg.index}")
        i += 1
    return " / ".join(parts) or "Document root"


def group_for(segments: list[Segment], *, container: bool = False) -> str:
    """Group by the root section. Unknown sections use their own (humanized) name;
    root-level scalars, which have no section, go to ``Other``."""
    if not segments or segments[0].key is None:
        return OTHER_GROUP
    root = segments[0].key
    if root.lower() in KNOWN_GROUPS:
        return KNOWN_GROUPS[root.lower()]
    if len(segments) == 1 and not container:
        return OTHER_GROUP
    return humanize_key(root)


def object_keys(segments: list[Segment]) -> list[str]:
    return [s.key for s in segments if s.key is not None]

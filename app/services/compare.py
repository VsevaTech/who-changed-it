"""Use-case layer: raw inputs in, :class:`DiffReport` out. Keeps routes thin."""

from __future__ import annotations

from app.models.diff import DiffReport
from app.services.array_matcher import DEFAULT_IDENTITY_KEYS
from app.services.diff_engine import semantic_diff
from app.services.parser import parse_json


def compare_texts(
    before_text: str | bytes,
    after_text: str | bytes,
    identity_keys: tuple[str, ...] = DEFAULT_IDENTITY_KEYS,
) -> DiffReport:
    """Parse both inputs and return the semantic diff. Raises ``JsonInputError``."""
    before = parse_json(before_text, side="Before")
    after = parse_json(after_text, side="After")
    return semantic_diff(before, after, identity_keys)


def parse_identity_keys(raw: str | None) -> tuple[str, ...]:
    """``"id, code, sku"`` → ``("id", "code", "sku")``; empty → defaults."""
    if not raw or not raw.strip():
        return DEFAULT_IDENTITY_KEYS
    keys = tuple(k.strip() for k in raw.split(",") if k.strip())
    return keys or DEFAULT_IDENTITY_KEYS

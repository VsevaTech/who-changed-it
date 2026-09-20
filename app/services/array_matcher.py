"""Semantic matching of array elements.

For arrays of objects we try to find an *identity key*: a key that is present in every
element on both sides, holds a scalar (string/number) value and is unique within each
array. Elements are then paired by that key regardless of their position.

If no such key exists we fall back to positional comparison and say so explicitly.
No heuristics beyond that — a wrong match is worse than an honest positional diff.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app import settings
from app.models.diff import MatchMode

Pair = tuple[Any | None, Any | None]  # (before_element, after_element); None = missing


@dataclass(frozen=True)
class MatchResult:
    mode: MatchMode
    identity_key: str | None
    # Ordered list of (identity_value_or_index, before, after)
    pairs: list[tuple[Any, Any | None, Any | None]] = field(default_factory=list)


def _identity_value(value: Any) -> Any:
    """Hashable, type-aware form of a scalar so `"1"` and `1` never collide."""
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int | Decimal):
        return ("num", Decimal(value))
    return ("str", value)


def _is_identity_candidate(key: str, elements: Sequence[dict[str, Any]]) -> bool:
    seen: set[Any] = set()
    for el in elements:
        if key not in el:
            return False
        value = el[key]
        if value is None or isinstance(value, bool | dict | list):
            return False
        ident = _identity_value(value)
        if ident in seen:
            return False
        seen.add(ident)
    return True


def find_identity_key(
    before: Sequence[Any],
    after: Sequence[Any],
    candidates: Sequence[str] = settings.DEFAULT_IDENTITY_KEYS,
) -> str | None:
    """Return the first candidate key usable as identity for both arrays, else None."""
    if not before and not after:
        return None
    if not all(isinstance(el, dict) for el in before):
        return None
    if not all(isinstance(el, dict) for el in after):
        return None
    for key in candidates:
        if _is_identity_candidate(key, before) and _is_identity_candidate(key, after):
            return key
    return None


def match_arrays(
    before: Sequence[Any],
    after: Sequence[Any],
    candidates: Sequence[str] = settings.DEFAULT_IDENTITY_KEYS,
) -> MatchResult:
    key = find_identity_key(before, after, candidates)
    if key is None:
        pairs: list[tuple[Any, Any | None, Any | None]] = []
        for i in range(max(len(before), len(after))):
            b = before[i] if i < len(before) else None
            a = after[i] if i < len(after) else None
            pairs.append((i, b, a))
        return MatchResult(mode=MatchMode.POSITION, identity_key=None, pairs=pairs)

    after_by_id: dict[Any, Any] = {_identity_value(el[key]): el for el in after}
    before_ids = {_identity_value(el[key]) for el in before}

    pairs = []
    # Elements present before (kept or removed), in "before" order.
    for el in before:
        ident = _identity_value(el[key])
        pairs.append((el[key], el, after_by_id.get(ident)))
    # Newly added elements, in "after" order.
    for el in after:
        if _identity_value(el[key]) not in before_ids:
            pairs.append((el[key], None, el))
    return MatchResult(mode=MatchMode.IDENTITY, identity_key=key, pairs=pairs)

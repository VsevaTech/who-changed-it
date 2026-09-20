"""Semantic matching of array elements between two versions of a configuration.

The core rule: never compare arrays by position when a *reliable* identity is available.

* Arrays of objects are matched by the first configurable identity key that is present in
  **every** element on both sides, holds a scalar value and is **unique** within each side.
* Arrays of scalars whose values are unique on each side are matched by value.
* Everything else (mixed arrays, nested arrays, missing/duplicated keys) falls back to
  positional comparison, and the caller is told so explicitly — we do not guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.models.diff import MatchStrategy

DEFAULT_IDENTITY_KEYS: tuple[str, ...] = (
    "id",
    "uuid",
    "code",
    "key",
    "name",
    "tid",
    "terminal_id",
    "company_id",
    "location_id",
)

Scalar = str | int | Decimal | bool


def _is_scalar(value: Any) -> bool:
    return isinstance(value, str | int | Decimal | bool) and value is not None


def _scalar_key(value: Any) -> tuple[str, str]:
    """Hashable, type-aware key so that ``"1"`` and ``1`` never collide."""
    if isinstance(value, bool):
        return ("bool", str(value))
    if isinstance(value, int):
        return ("num", str(Decimal(value)))
    if isinstance(value, Decimal):
        return ("num", str(value.normalize()) if value != 0 else "0")
    return ("str", value)


@dataclass
class MatchedPair:
    identity: str | None  # e.g. "id=T2" or "0" for positional
    before: Any
    after: Any
    before_index: int | None
    after_index: int | None


@dataclass
class ArrayMatch:
    strategy: MatchStrategy
    identity_key: str | None
    pairs: list[MatchedPair] = field(default_factory=list)
    added: list[MatchedPair] = field(default_factory=list)
    removed: list[MatchedPair] = field(default_factory=list)


def find_identity_key(
    before: list[Any], after: list[Any], candidates: tuple[str, ...] = DEFAULT_IDENTITY_KEYS
) -> str | None:
    """Return the first candidate that is a reliable identity for both arrays, else ``None``."""
    items = [*before, *after]
    if not items or not all(isinstance(i, dict) and i for i in items):
        return None

    for key in candidates:
        if not all(key in item and _is_scalar(item[key]) for item in items):
            continue
        before_keys = [_scalar_key(i[key]) for i in before]
        after_keys = [_scalar_key(i[key]) for i in after]
        if len(set(before_keys)) == len(before_keys) and len(set(after_keys)) == len(after_keys):
            return key
    return None


def _format_identity_value(value: Scalar) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def match_arrays(
    before: list[Any], after: list[Any], candidates: tuple[str, ...] = DEFAULT_IDENTITY_KEYS
) -> ArrayMatch:
    """Pair the elements of *before* and *after* using the most reliable strategy available."""
    key = find_identity_key(before, after, candidates)
    if key is not None:
        return _match_by_identity(before, after, key)

    if before or after:
        all_scalars = all(_is_scalar(x) for x in [*before, *after])
        if all_scalars:
            b_keys = [_scalar_key(x) for x in before]
            a_keys = [_scalar_key(x) for x in after]
            if len(set(b_keys)) == len(b_keys) and len(set(a_keys)) == len(a_keys):
                return _match_by_value(before, after)

    return _match_by_position(before, after)


def _match_by_identity(before: list[dict], after: list[dict], key: str) -> ArrayMatch:
    result = ArrayMatch(strategy=MatchStrategy.IDENTITY, identity_key=key)
    after_by_key = {_scalar_key(item[key]): (idx, item) for idx, item in enumerate(after)}
    seen: set[tuple[str, str]] = set()

    for b_idx, b_item in enumerate(before):
        k = _scalar_key(b_item[key])
        identity = f"{key}={_format_identity_value(b_item[key])}"
        if k in after_by_key:
            a_idx, a_item = after_by_key[k]
            seen.add(k)
            result.pairs.append(MatchedPair(identity, b_item, a_item, b_idx, a_idx))
        else:
            result.removed.append(MatchedPair(identity, b_item, None, b_idx, None))

    for a_idx, a_item in enumerate(after):
        k = _scalar_key(a_item[key])
        if k not in seen:
            identity = f"{key}={_format_identity_value(a_item[key])}"
            result.added.append(MatchedPair(identity, None, a_item, None, a_idx))
    return result


def _match_by_value(before: list[Scalar], after: list[Scalar]) -> ArrayMatch:
    result = ArrayMatch(strategy=MatchStrategy.VALUE, identity_key=None)
    after_keys = {_scalar_key(x): idx for idx, x in enumerate(after)}
    before_keys = {_scalar_key(x): idx for idx, x in enumerate(before)}

    for b_idx, x in enumerate(before):
        k = _scalar_key(x)
        if k in after_keys:
            result.pairs.append(MatchedPair(None, x, x, b_idx, after_keys[k]))
        else:
            result.removed.append(MatchedPair(None, x, None, b_idx, None))
    for a_idx, x in enumerate(after):
        if _scalar_key(x) not in before_keys:
            result.added.append(MatchedPair(None, None, x, None, a_idx))
    return result


def _match_by_position(before: list[Any], after: list[Any]) -> ArrayMatch:
    result = ArrayMatch(strategy=MatchStrategy.POSITION, identity_key=None)
    common = min(len(before), len(after))
    for i in range(common):
        result.pairs.append(MatchedPair(str(i), before[i], after[i], i, i))
    for i in range(common, len(before)):
        result.removed.append(MatchedPair(str(i), before[i], None, i, None))
    for i in range(common, len(after)):
        result.added.append(MatchedPair(str(i), None, after[i], None, i))
    return result

"""Value comparison and rendering helpers.

The rules are intentionally strict:
* `"30"` (string) and `30` (number) are different values.
* `true` and `1` are different values (Python would say `True == 1`; we do not).
* `30` and `30.0` are the same numeric value (both are JSON numbers).
* Object key order and whitespace never matter.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import simplejson

_NUMBER_TYPES = (int, Decimal)


def is_number(value: Any) -> bool:
    return isinstance(value, _NUMBER_TYPES) and not isinstance(value, bool)


def is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, bool | int | Decimal | str)


def values_equal(a: Any, b: Any) -> bool:
    """Deep, type-aware equality for parsed JSON values."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if is_number(a) and is_number(b):
        return a == b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        if a.keys() != b.keys():
            return False
        return all(values_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(values_equal(x, y) for x, y in zip(a, b, strict=True))
    return False


def to_json_text(value: Any, *, indent: int | None = None) -> str:
    """Serialize a parsed JSON value back to text, keeping Decimals exact."""
    return simplejson.dumps(
        value,
        use_decimal=True,
        indent=indent,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ": ") if indent else (", ", ": "),
    )


def render_value(value: Any) -> str:
    """Short human-oriented rendering of a value for UI/report."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if is_number(value):
        return str(value)
    if isinstance(value, str):
        return value if value != "" else '""'
    if isinstance(value, dict):
        if not value:
            return "{}"
        return f"{{…}} ({len(value)} field{'s' if len(value) != 1 else ''})"
    if isinstance(value, list):
        if not value:
            return "[]"
        return f"[…] ({len(value)} item{'s' if len(value) != 1 else ''})"
    return str(value)

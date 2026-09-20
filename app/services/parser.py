"""Safe JSON parsing with size limits and Decimal-preserving numbers."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from app import settings

JsonValue = None | bool | int | Decimal | str | list[Any] | dict[str, Any]


class JsonParseError(ValueError):
    """Raised when input cannot be accepted. The message is safe to show to users."""


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > settings.MAX_DEPTH:
        raise JsonParseError(f"JSON is nested deeper than {settings.MAX_DEPTH} levels")
    if isinstance(value, dict):
        for v in value.values():
            _check_depth(v, depth + 1)
    elif isinstance(value, list):
        for v in value:
            _check_depth(v, depth + 1)


def parse_json(raw: str | bytes, *, label: str = "JSON") -> JsonValue:
    """Parse a JSON document.

    * Rejects documents larger than `settings.MAX_JSON_BYTES`.
    * Numbers with a fractional part or exponent are parsed as `Decimal`, never `float`,
      so `12.30` stays `12.30`.
    * Integers stay `int`. Booleans stay `bool`. `null` becomes `None`.
    * Duplicate object keys are rejected (they make the diff ambiguous).
    """
    data = raw.encode("utf-8") if isinstance(raw, str) else raw

    if len(data) > settings.MAX_JSON_BYTES:
        limit_mb = settings.MAX_JSON_BYTES // (1024 * 1024)
        raise JsonParseError(f"{label} is too large (limit {limit_mb} MB)")

    if isinstance(raw, bytes):
        try:
            text = data.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError as exc:
            raise JsonParseError(f"{label} is not valid UTF-8") from exc
    else:
        text = raw
    if text.startswith("﻿"):
        text = text[1:]
    if not text.strip():
        raise JsonParseError(f"{label} is empty")

    def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise JsonParseError(f"{label} contains duplicate key '{key}'")
            result[key] = value
        return result

    try:
        value = json.loads(
            text,
            parse_float=Decimal,
            parse_constant=_reject_non_finite,
            object_pairs_hook=_reject_duplicates,
        )
    except JsonParseError:
        raise
    except json.JSONDecodeError as exc:
        raise JsonParseError(
            f"{label} is not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})"
        ) from exc

    _check_depth(value)
    return value


def _reject_non_finite(token: str) -> Any:
    raise JsonParseError(f"non-standard JSON literal '{token}' is not allowed")

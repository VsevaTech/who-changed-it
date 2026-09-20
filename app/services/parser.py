"""JSON parsing with friendly errors, size limits and Decimal-safe numbers.

Floats are parsed as :class:`decimal.Decimal` so that potentially financial values
(``12.50``, ``0.1``) are never rounded through binary floating point. Integers stay ``int``.
"""

from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

DEFAULT_MAX_BYTES = int(os.environ.get("WCI_MAX_INPUT_BYTES", str(2 * 1024 * 1024)))
MAX_DEPTH = int(os.environ.get("WCI_MAX_DEPTH", "200"))


class JsonInputError(ValueError):
    """Raised when an input cannot be used for comparison. Message is safe to show to users."""

    def __init__(self, side: str, message: str):
        self.side = side
        super().__init__(f"{side}: {message}")
        self.user_message = message


def _check_depth(value: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ValueError(f"JSON is nested deeper than {MAX_DEPTH} levels")
    if isinstance(value, dict):
        for v in value.values():
            _check_depth(v, depth + 1)
    elif isinstance(value, list):
        for v in value:
            _check_depth(v, depth + 1)


def parse_json(text: str | bytes, *, side: str = "input", max_bytes: int | None = None) -> Any:
    """Parse *text* into Python data.

    * ``null`` is a valid document and yields ``None``.
    * Floats become ``Decimal``; integers stay ``int``; booleans stay ``bool``.
    * Raises :class:`JsonInputError` with a human-readable message on any problem.
    """
    limit = max_bytes if max_bytes is not None else DEFAULT_MAX_BYTES

    if isinstance(text, bytes):
        if len(text) > limit:
            raise JsonInputError(side, f"file is larger than {limit // 1024} KB limit")
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise JsonInputError(side, "file is not valid UTF-8 text") from None
    else:
        if len(text.encode("utf-8")) > limit:
            raise JsonInputError(side, f"input is larger than {limit // 1024} KB limit")

    if not text.strip():
        raise JsonInputError(side, "input is empty — paste or upload a JSON document")

    try:
        data = json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise JsonInputError(
            side, f"invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from None
    except RecursionError:
        raise JsonInputError(side, f"JSON is nested deeper than {MAX_DEPTH} levels") from None

    try:
        _check_depth(data)
    except (ValueError, RecursionError) as exc:
        raise JsonInputError(side, str(exc) or "JSON is nested too deeply") from None

    return data

"""Use-case layer: raw input -> DiffResult. Keeps FastAPI routes free of business logic."""

from __future__ import annotations

from app.models.diff import DiffResult
from app.services.diff_engine import DiffOptions, diff_json
from app.services.parser import JsonParseError, parse_json


class CompareError(ValueError):
    """User-facing error (safe to display); carries which side failed."""

    def __init__(self, side: str, message: str) -> None:
        super().__init__(message)
        self.side = side
        self.message = message


def compare_documents(
    before_raw: str | bytes,
    after_raw: str | bytes,
    options: DiffOptions | None = None,
) -> DiffResult:
    try:
        before = parse_json(before_raw, label="BEFORE")
    except JsonParseError as exc:
        raise CompareError("before", str(exc)) from exc
    try:
        after = parse_json(after_raw, label="AFTER")
    except JsonParseError as exc:
        raise CompareError("after", str(exc)) from exc
    return diff_json(before, after, options)

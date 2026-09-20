from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.models.diff import DiffResult
from app.services.compare import compare_documents

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def diff(before: Any, after: Any) -> DiffResult:
    """Round-trip through JSON text so tests exercise the real parser."""
    return compare_documents(json.dumps(before), json.dumps(after))


@pytest.fixture
def example_pair() -> tuple[bytes, bytes]:
    return (
        (EXAMPLES / "merchant-before.json").read_bytes(),
        (EXAMPLES / "merchant-after.json").read_bytes(),
    )

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from app.models.diff import DiffReport
from app.services.diff_engine import semantic_diff

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def loads(text: str) -> Any:
    return json.loads(text, parse_float=Decimal)


def diff(before: Any, after: Any) -> DiffReport:
    return semantic_diff(before, after)


def paths(report: DiffReport) -> list[str]:
    return [c.path for c in report.changes]


@pytest.fixture
def demo_before() -> bytes:
    return (EXAMPLES / "merchant-before.json").read_bytes()


@pytest.fixture
def demo_after() -> bytes:
    return (EXAMPLES / "merchant-after.json").read_bytes()

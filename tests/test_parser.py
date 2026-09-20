from __future__ import annotations

from decimal import Decimal

import pytest

from app import settings
from app.services.compare import CompareError, compare_documents
from app.services.parser import JsonParseError, parse_json


def test_invalid_json_raises_readable_error():
    with pytest.raises(JsonParseError) as exc:
        parse_json('{"a": 1,}', label="BEFORE")
    msg = str(exc.value)
    assert "BEFORE is not valid JSON" in msg
    assert "line 1" in msg


def test_compare_reports_which_side_failed():
    with pytest.raises(CompareError) as exc:
        compare_documents("{}", "{oops")
    assert exc.value.side == "after"
    with pytest.raises(CompareError) as exc:
        compare_documents("not json", "{}")
    assert exc.value.side == "before"


def test_empty_input_is_rejected():
    with pytest.raises(JsonParseError, match="empty"):
        parse_json("   ")


def test_null_document_is_supported():
    assert parse_json("null") is None
    assert compare_documents("null", "null").summary.total == 0
    assert compare_documents("null", "{}").summary.total == 1


def test_all_json_types():
    v = parse_json('{"s": "x", "n": 1, "d": 1.5, "b": true, "z": null, "l": [1], "o": {}}')
    assert v == {"s": "x", "n": 1, "d": Decimal("1.5"), "b": True, "z": None, "l": [1], "o": {}}
    assert isinstance(v["d"], Decimal)
    assert isinstance(v["n"], int)


def test_size_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_JSON_BYTES", 10)
    with pytest.raises(JsonParseError, match="too large"):
        parse_json('{"aaaaaaaaaaaa": 1}')


def test_duplicate_keys_rejected():
    with pytest.raises(JsonParseError, match="duplicate key"):
        parse_json('{"a": 1, "a": 2}')


def test_nan_and_infinity_rejected():
    with pytest.raises(JsonParseError):
        parse_json("[NaN]")
    with pytest.raises(JsonParseError):
        parse_json("[Infinity]")


def test_bom_and_bytes_input():
    assert parse_json(b'\xef\xbb\xbf{"a": 1}') == {"a": 1}
    assert parse_json('﻿{"a": 1}') == {"a": 1}


def test_invalid_utf8_bytes():
    with pytest.raises(JsonParseError, match="UTF-8"):
        parse_json(b'{"a": "\xff"}')


def test_depth_limit(monkeypatch):
    monkeypatch.setattr(settings, "MAX_DEPTH", 3)
    with pytest.raises(JsonParseError, match="nested deeper"):
        parse_json('{"a": {"b": {"c": {"d": {"e": 1}}}}}')

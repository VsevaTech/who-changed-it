from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.parser import JsonInputError, parse_json


def test_invalid_json_gives_friendly_error():
    with pytest.raises(JsonInputError) as exc:
        parse_json('{"a": 1,}', side="Before")
    assert exc.value.side == "Before"
    assert "line 1" in exc.value.user_message
    assert "column" in exc.value.user_message


def test_empty_input_is_an_error():
    with pytest.raises(JsonInputError):
        parse_json("   \n", side="After")


def test_null_document_is_valid():
    assert parse_json("null") is None


def test_all_json_types_supported():
    data = parse_json('{"o": {}, "a": [1, "s", true, null, 2.50], "n": 3, "b": false}')
    assert data["o"] == {}
    assert data["a"] == [1, "s", True, None, Decimal("2.50")]
    assert isinstance(data["a"][4], Decimal)
    assert isinstance(data["n"], int)


def test_floats_are_decimal_not_float():
    data = parse_json('{"fee": 0.1}')
    assert isinstance(data["fee"], Decimal)
    assert str(data["fee"]) == "0.1"


def test_size_limit_enforced():
    big = '{"a": "' + "x" * 200 + '"}'
    with pytest.raises(JsonInputError) as exc:
        parse_json(big, max_bytes=100)
    assert "KB limit" in exc.value.user_message


def test_bytes_with_bom_and_bad_utf8():
    assert parse_json(b"\xef\xbb\xbf{}") == {}
    with pytest.raises(JsonInputError):
        parse_json(b"\xff\xfe{}")


def test_depth_limit():
    deep = "[" * 500 + "]" * 500
    with pytest.raises(JsonInputError) as exc:
        parse_json(deep)
    assert "deep" in exc.value.user_message

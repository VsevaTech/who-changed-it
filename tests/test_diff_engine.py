"""Core semantic diff behaviour on primitives, objects and nesting."""

from __future__ import annotations

from decimal import Decimal

from app.models.diff import ChangeType
from tests.conftest import diff, loads, paths


def test_identical_json_has_no_changes():
    doc = loads('{"a": 1, "b": {"c": [1, 2, {"id": "x", "v": true}]}, "d": null}')
    report = diff(doc, loads('{"a": 1, "b": {"c": [1, 2, {"id": "x", "v": true}]}, "d": null}'))
    assert report.summary.total == 0
    assert report.changes == []


def test_changed_primitive():
    report = diff({"timeout": 30}, {"timeout": 10})
    assert report.summary.total == 1
    change = report.changes[0]
    assert change.type is ChangeType.CHANGED
    assert change.path == "timeout"
    assert (change.old_value, change.new_value) == (30, 10)


def test_added_field():
    report = diff({"a": 1}, {"a": 1, "email": "billing@example.com"})
    assert paths(report) == ["email"]
    assert report.changes[0].type is ChangeType.ADDED
    assert report.changes[0].old_value is None
    assert report.changes[0].new_value == "billing@example.com"
    assert report.summary.added == 1


def test_removed_field():
    report = diff({"a": 1, "b": 2}, {"a": 1})
    assert paths(report) == ["b"]
    assert report.changes[0].type is ChangeType.REMOVED
    assert report.changes[0].old_value == 2
    assert report.summary.removed == 1


def test_nested_change():
    before = loads('{"company": {"payment_settings": {"timeout": 30, "mode": "auto"}}}')
    after = loads('{"company": {"payment_settings": {"timeout": 10, "mode": "auto"}}}')
    report = diff(before, after)
    assert paths(report) == ["company.payment_settings.timeout"]
    assert report.changes[0].display_path == "Company / Payment settings / Timeout"
    assert report.changes[0].group == "Company"


def test_null_to_value():
    report = diff({"x": None}, {"x": 5})
    assert report.summary.changed == 1
    assert report.changes[0].old_value is None
    assert report.changes[0].new_value == 5


def test_value_to_null():
    report = diff({"x": "abc"}, {"x": None})
    assert report.summary.changed == 1
    assert report.changes[0].old_value == "abc"
    assert report.changes[0].new_value is None


def test_null_document_does_not_crash():
    assert diff(None, None).summary.total == 0
    report = diff(None, {"a": 1})
    assert report.summary.total == 1
    assert report.changes[0].path == "$"


def test_boolean_change():
    report = diff({"google_pay": False}, {"google_pay": True})
    assert report.summary.changed == 1
    assert report.changes[0].old_value is False
    assert report.changes[0].new_value is True


def test_boolean_is_not_number():
    # true != 1, false != 0
    assert diff({"x": True}, {"x": 1}).summary.total == 1
    assert diff({"x": False}, {"x": 0}).summary.total == 1


def test_string_30_differs_from_number_30():
    report = diff({"timeout": "30"}, {"timeout": 30})
    assert report.summary.changed == 1
    assert report.changes[0].old_value == "30"
    assert report.changes[0].new_value == 30


def test_numeric_equality_is_decimal_not_float():
    # 0.1 + 0.2 style traps must not produce false changes or false equality.
    assert diff(loads('{"a": 0.1}'), loads('{"a": 0.10}')).summary.total == 0
    assert diff(loads('{"a": 0.1}'), loads('{"a": 0.1000000000000000055}')).summary.total == 1
    assert diff(loads('{"a": 1.00}'), loads('{"a": 1}')).summary.total == 0


def test_decimal_values_are_preserved():
    report = diff(loads('{"fee": 1.75}'), loads('{"fee": 1.80}'))
    assert isinstance(report.changes[0].old_value, Decimal)
    assert report.changes[0].new_value == Decimal("1.80")


def test_object_key_reorder_is_not_a_change():
    before = loads('{"a": 1, "b": {"x": 1, "y": 2}, "c": [1, 2]}')
    after = loads('{"c": [1, 2], "b": {"y": 2, "x": 1}, "a": 1}')
    assert diff(before, after).summary.total == 0


def test_whitespace_and_formatting_are_not_changes():
    before = loads('{"a":1,"b":[1,2]}')
    after = loads('{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}')
    assert diff(before, after).summary.total == 0


def test_type_change_object_to_scalar():
    report = diff({"x": {"a": 1}}, {"x": "flat"})
    assert report.summary.changed == 1
    assert report.changes[0].old_value == {"a": 1}
    assert report.changes[0].new_value == "flat"


def test_empty_object_and_empty_array():
    assert diff({}, {}).summary.total == 0
    assert diff([], []).summary.total == 0
    assert diff({"a": []}, {"a": []}).summary.total == 0
    assert diff({"a": {}}, {"a": {}}).summary.total == 0
    report = diff({"a": []}, {"a": {}})
    assert report.summary.changed == 1


def test_removed_subtree_is_a_single_change():
    before = {"billing": {"email": "a@b.c", "plan": "pro"}}
    report = diff(before, {})
    assert paths(report) == ["billing"]
    assert report.changes[0].type is ChangeType.REMOVED
    assert report.changes[0].old_value == {"email": "a@b.c", "plan": "pro"}


def test_deterministic_ordering():
    before = {"z": 1, "a": 1, "m": {"k": 1}}
    after = {"z": 2, "a": 2, "m": {"k": 2}}
    first = diff(before, after)
    second = diff(dict(reversed(list(before.items()))), after)
    assert paths(first) == paths(second) == ["a", "m.k", "z"]


def test_groups_known_and_unknown_sections():
    before = {"payment_settings": {"t": 1}, "loyalty_program": {"tier": 1}, "version": 1}
    after = {"payment_settings": {"t": 2}, "loyalty_program": {"tier": 2}, "version": 2}
    groups = {c.path: c.group for c in diff(before, after).changes}
    assert groups["payment_settings.t"] == "Payments"
    assert groups["loyalty_program.tier"] == "Loyalty program"
    assert groups["version"] == "Other"

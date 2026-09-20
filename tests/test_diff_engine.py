"""Core semantic diff behaviour on objects and primitives."""

from __future__ import annotations

from decimal import Decimal

from app.models.diff import ChangeType
from app.services.compare import compare_documents
from tests.conftest import diff


def test_identical_json_has_no_changes():
    doc = {"a": 1, "b": {"c": [1, 2, 3]}, "d": None}
    assert diff(doc, doc).summary.total == 0


def test_changed_primitive():
    r = diff({"timeout": 30}, {"timeout": 10})
    assert r.summary.total == 1
    c = r.changes[0]
    assert c.type is ChangeType.CHANGED
    assert c.path == "timeout"
    assert (c.old_value, c.new_value) == (30, 10)


def test_added_field():
    r = diff({}, {"email": "x@example.com"})
    assert [(c.type, c.path, c.new_value) for c in r.changes] == [
        (ChangeType.ADDED, "email", "x@example.com")
    ]
    assert r.summary.added == 1


def test_removed_field():
    r = diff({"email": "x@example.com"}, {})
    assert [(c.type, c.path, c.old_value) for c in r.changes] == [
        (ChangeType.REMOVED, "email", "x@example.com")
    ]
    assert r.summary.removed == 1


def test_nested_change():
    before = {"payments": {"timeout": 30, "google_pay": False}}
    after = {"payments": {"timeout": 10, "google_pay": True}}
    r = diff(before, after)
    assert r.summary.total == 2
    paths = {c.path: (c.old_value, c.new_value) for c in r.changes}
    assert paths == {"payments.timeout": (30, 10), "payments.google_pay": (False, True)}
    assert all(c.type is ChangeType.CHANGED for c in r.changes)


def test_null_to_value():
    r = diff({"x": None}, {"x": 5})
    assert r.summary.changed == 1
    assert (r.changes[0].old_value, r.changes[0].new_value) == (None, 5)


def test_value_to_null():
    r = diff({"x": "abc"}, {"x": None})
    assert r.summary.changed == 1
    assert (r.changes[0].old_value, r.changes[0].new_value) == ("abc", None)


def test_boolean_change():
    r = diff({"enabled": False}, {"enabled": True})
    assert r.summary.changed == 1
    assert r.changes[0].display_path == "Enabled"


def test_string_30_vs_number_30_is_a_change():
    r = diff({"timeout": "30"}, {"timeout": 30})
    assert r.summary.changed == 1
    assert r.changes[0].old_value == "30"
    assert r.changes[0].new_value == 30


def test_true_vs_1_is_a_change():
    assert diff({"flag": True}, {"flag": 1}).summary.total == 1
    assert diff({"flag": 0}, {"flag": False}).summary.total == 1


def test_object_key_reorder_is_not_a_change():
    before = '{"a": 1, "b": {"c": 2, "d": 3}}'
    after = '{"b": {"d": 3, "c": 2}, "a": 1}'
    assert compare_documents(before, after).summary.total == 0


def test_whitespace_and_formatting_are_not_changes():
    before = '{"a":1,"b":[1,2]}'
    after = '{\n  "a": 1,\n  "b": [\n    1,\n    2\n  ]\n}\n'
    assert compare_documents(before, after).summary.total == 0


def test_decimal_values_are_exact():
    r = compare_documents('{"amount": 12.30}', '{"amount": 12.31}')
    assert r.summary.total == 1
    assert r.changes[0].old_value == Decimal("12.30")
    assert isinstance(r.changes[0].old_value, Decimal)
    # Same numeric value written differently is not a change.
    assert compare_documents('{"amount": 12.30}', '{"amount": 12.3}').summary.total == 0
    assert compare_documents('{"amount": 30}', '{"amount": 30.0}').summary.total == 0


def test_type_change_object_to_scalar():
    r = diff({"x": {"a": 1}}, {"x": "flat"})
    assert r.summary.changed == 1
    assert r.changes[0].old_value == {"a": 1}


def test_empty_object_and_empty_array():
    assert diff({}, {}).summary.total == 0
    assert diff([], []).summary.total == 0
    assert diff({"a": []}, {"a": []}).summary.total == 0
    assert diff({"a": {}}, {"a": {}}).summary.total == 0
    r = diff({"a": []}, {"a": {}})
    assert r.summary.changed == 1


def test_root_scalars():
    assert diff(1, 1).summary.total == 0
    r = diff(1, 2)
    assert r.summary.total == 1
    assert r.changes[0].path == "$"
    assert r.changes[0].group == "Other"


def test_deterministic_output():
    before = {"z": 1, "a": {"y": [3, 2, 1], "x": 0}, "m": [{"id": 2}, {"id": 1}]}
    after = {"m": [{"id": 1, "v": 1}, {"id": 3}], "a": {"x": 1, "y": [1, 2, 3]}, "z": 2}
    first = diff(before, after).model_dump()
    for _ in range(5):
        assert diff(before, after).model_dump() == first


def test_groups_use_known_sections_and_fallback():
    r = diff(
        {"company": {"n": 1}, "payment_settings": {"t": 1}, "custom_module": {"k": 1}, "q": 1},
        {"company": {"n": 2}, "payment_settings": {"t": 2}, "custom_module": {"k": 2}, "q": 2},
    )
    groups = {c.path: c.group for c in r.changes}
    assert groups["company.n"] == "Company"
    assert groups["payment_settings.t"] == "Payments"
    assert groups["custom_module.k"] == "Custom module"
    assert groups["q"] == "Q"
    assert [g for g, _ in r.groups] == ["Company", "Payments", "Custom module", "Q"]


def test_display_path_humanization():
    r = diff(
        {"company": {"payment_settings": {"timeout": 1}}},
        {"company": {"payment_settings": {"timeout": 2}}},
    )
    assert r.changes[0].display_path == "Company / Payment settings / Timeout"
    assert r.changes[0].path == "company.payment_settings.timeout"

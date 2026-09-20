"""Semantic array matching — the key feature."""

from __future__ import annotations

from app.models.diff import ChangeType, MatchStrategy
from app.services.array_matcher import find_identity_key, match_arrays
from app.services.diff_engine import POSITIONAL_NOTE, semantic_diff
from tests.conftest import diff, loads, paths


def test_critical_reorder_with_id_has_zero_changes():
    before = loads('{"terminals": [{"id": "T1", "tid": "1001"}, {"id": "T2", "tid": "1002"}]}')
    after = loads('{"terminals": [{"id": "T2", "tid": "1002"}, {"id": "T1", "tid": "1001"}]}')
    report = diff(before, after)
    assert report.summary.total == 0
    assert report.notes == []


def test_critical_reorder_plus_one_change():
    before = loads('{"terminals": [{"id": "T1", "tid": "1001"}, {"id": "T2", "tid": "1002"}]}')
    after = loads('{"terminals": [{"id": "T2", "tid": "9999"}, {"id": "T1", "tid": "1001"}]}')
    report = diff(before, after)
    assert report.summary.total == 1
    change = report.changes[0]
    assert change.type is ChangeType.CHANGED
    assert change.path == "terminals[id=T2].tid"
    assert change.display_path == "Terminal T2 / TID"
    assert (change.old_value, change.new_value) == ("1002", "9999")
    assert change.identity == "id=T2"
    assert change.note is None


def test_array_object_added():
    before = {"terminals": [{"id": "T1", "tid": "1"}]}
    after = {"terminals": [{"id": "T1", "tid": "1"}, {"id": "T2", "tid": "2"}]}
    report = diff(before, after)
    assert paths(report) == ["terminals[id=T2]"]
    assert report.changes[0].type is ChangeType.ADDED
    assert report.changes[0].new_value == {"id": "T2", "tid": "2"}
    assert report.changes[0].display_path == "Terminal T2"


def test_array_object_removed():
    before = {"terminals": [{"id": "T1", "tid": "1"}, {"id": "T2", "tid": "2"}]}
    after = {"terminals": [{"id": "T2", "tid": "2"}]}
    report = diff(before, after)
    assert paths(report) == ["terminals[id=T1]"]
    assert report.changes[0].type is ChangeType.REMOVED
    assert report.changes[0].old_value == {"id": "T1", "tid": "1"}


def test_array_without_identity_uses_positions_and_says_so():
    before = {"rules": [{"amount": 10, "action": "allow"}, {"amount": 20, "action": "block"}]}
    after = {"rules": [{"amount": 20, "action": "block"}, {"amount": 10, "action": "allow"}]}
    report = diff(before, after)
    # No reliable key → positional → the reorder IS reported, explicitly.
    assert report.summary.total == 4
    assert all(c.note == POSITIONAL_NOTE for c in report.changes)
    assert report.notes == [f"rules: {POSITIONAL_NOTE}"]
    assert paths(report) == [
        "rules[0].action",
        "rules[0].amount",
        "rules[1].action",
        "rules[1].amount",
    ]
    assert report.changes[0].display_path == "Rule #0 / Action"


def test_positional_added_and_removed_elements():
    report = diff({"r": [{"a": 1}]}, {"r": [{"a": 1}, {"a": 2}]})
    assert paths(report) == ["r[1]"]
    assert report.changes[0].type is ChangeType.ADDED
    report = diff({"r": [{"a": 1}, {"a": 2}]}, {"r": [{"a": 1}]})
    assert paths(report) == ["r[1]"]
    assert report.changes[0].type is ChangeType.REMOVED


def test_duplicate_identity_values_are_not_trusted():
    before = [{"id": "A", "v": 1}, {"id": "A", "v": 2}]
    after = [{"id": "A", "v": 2}, {"id": "A", "v": 1}]
    assert find_identity_key(before, after) is None
    assert match_arrays(before, after).strategy is MatchStrategy.POSITION


def test_identity_key_must_be_present_in_every_element():
    before = [{"id": "A", "v": 1}, {"v": 2}]
    after = [{"id": "A", "v": 1}, {"v": 2}]
    assert find_identity_key(before, after) is None


def test_identity_key_priority_order():
    before = [{"code": "X", "name": "n1"}, {"code": "Y", "name": "n2"}]
    after = [{"code": "Y", "name": "n2"}, {"code": "X", "name": "n1"}]
    assert find_identity_key(before, after) == "code"  # code precedes name in defaults


def test_custom_identity_keys():
    before = {"items": [{"sku": "A", "qty": 1}, {"sku": "B", "qty": 2}]}
    after = {"items": [{"sku": "B", "qty": 3}, {"sku": "A", "qty": 1}]}
    report = semantic_diff(before, after, identity_keys=("sku",))
    assert paths(report) == ["items[sku=B].qty"]
    assert report.changes[0].display_path == "Item B / Qty"


def test_identity_values_are_type_aware():
    # id "1" (string) and id 1 (number) are different elements.
    before = [{"id": "1", "v": "a"}]
    after = [{"id": 1, "v": "a"}]
    match = match_arrays(before, after)
    assert match.strategy is MatchStrategy.IDENTITY
    assert len(match.removed) == 1 and len(match.added) == 1


def test_scalar_array_reorder_with_unique_values_is_not_a_change():
    assert diff({"schemes": ["visa", "mc"]}, {"schemes": ["mc", "visa"]}).summary.total == 0


def test_scalar_array_added_and_removed_values():
    report = diff({"schemes": ["visa", "mc"]}, {"schemes": ["visa", "amex"]})
    assert report.summary.total == 2
    kinds = {c.type for c in report.changes}
    assert kinds == {ChangeType.ADDED, ChangeType.REMOVED}
    values = {c.old_value or c.new_value for c in report.changes}
    assert values == {"mc", "amex"}


def test_scalar_array_with_duplicates_falls_back_to_positions():
    report = diff({"a": [1, 1, 2]}, {"a": [1, 2, 1]})
    assert report.summary.total == 2
    assert all(c.note == POSITIONAL_NOTE for c in report.changes)


def test_scalar_array_string_vs_number_elements_differ():
    report = diff({"a": ["1"]}, {"a": [1]})
    assert report.summary.total == 2


def test_nested_arrays_by_identity():
    before = {
        "locations": [
            {"id": "L1", "terminals": [{"id": "T1", "tid": "1"}, {"id": "T2", "tid": "2"}]}
        ]
    }
    after = {
        "locations": [
            {"id": "L1", "terminals": [{"id": "T2", "tid": "2"}, {"id": "T1", "tid": "7"}]}
        ]
    }
    report = diff(before, after)
    assert paths(report) == ["locations[id=L1].terminals[id=T1].tid"]
    assert report.changes[0].display_path == "Location L1 / Terminal T1 / TID"
    assert report.changes[0].identity == "id=T1"


def test_array_of_arrays_is_positional():
    report = diff({"m": [[1, 2], [3, 4]]}, {"m": [[3, 4], [1, 2]]})
    assert report.summary.total > 0
    assert all(c.note == POSITIONAL_NOTE for c in report.changes)


def test_mixed_array_is_positional():
    match = match_arrays([{"id": 1}, "x"], [{"id": 1}, "x"])
    assert match.strategy is MatchStrategy.POSITION


def test_empty_arrays_match_trivially():
    match = match_arrays([], [])
    assert match.pairs == [] and match.added == [] and match.removed == []
    assert diff({"a": []}, {"a": [{"id": 1}]}).summary.added == 1

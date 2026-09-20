"""Semantic array matching — the key feature."""

from __future__ import annotations

from app.models.diff import ChangeType, MatchMode
from app.services.array_matcher import find_identity_key, match_arrays
from app.services.diff_engine import POSITIONAL_NOTE, DiffOptions, diff_json
from tests.conftest import diff

T1 = {"id": "T1", "tid": "1001"}
T2 = {"id": "T2", "tid": "1002"}


def test_critical_reorder_with_id_gives_zero_changes():
    before = {"terminals": [T1, T2]}
    after = {"terminals": [T2, T1]}
    r = diff(before, after)
    assert r.summary.total == 0
    assert r.positional_arrays == []


def test_critical_reorder_plus_change_gives_exactly_one_change():
    before = {"terminals": [T1, T2]}
    after = {"terminals": [{"id": "T2", "tid": "9999"}, T1]}
    r = diff(before, after)
    assert r.summary.total == 1
    c = r.changes[0]
    assert c.type is ChangeType.CHANGED
    assert c.path == "terminals[id=T2].tid"
    assert c.display_path == "Terminal T2 / TID"
    assert (c.old_value, c.new_value) == ("1002", "9999")
    assert c.identity is not None and (c.identity.key, c.identity.value) == ("id", "T2")
    assert c.match_mode is MatchMode.IDENTITY
    assert c.note is None


def test_array_object_added():
    r = diff({"terminals": [T1]}, {"terminals": [T1, T2]})
    assert r.summary.added == 1 and r.summary.total == 1
    c = r.changes[0]
    assert c.path == "terminals[id=T2]"
    assert c.display_path == "Terminal T2"
    assert c.new_value == T2


def test_array_object_removed():
    r = diff({"terminals": [T1, T2]}, {"terminals": [T1]})
    assert r.summary.removed == 1 and r.summary.total == 1
    c = r.changes[0]
    assert c.path == "terminals[id=T2]"
    assert c.old_value == T2


def test_array_without_identity_uses_positional_comparison():
    before = {"steps": [{"action": "auth"}, {"action": "capture"}]}
    after = {"steps": [{"action": "capture"}, {"action": "auth"}]}
    r = diff(before, after)
    assert r.summary.total == 2
    assert r.positional_arrays == ["steps"]
    for c in r.changes:
        assert c.match_mode is MatchMode.POSITION
        assert c.note == POSITIONAL_NOTE
    assert {c.path for c in r.changes} == {"steps[0].action", "steps[1].action"}
    assert r.changes[0].display_path == "Step #1 / Action"


def test_positional_array_length_change():
    r = diff({"tags": ["a", "b"]}, {"tags": ["a", "b", "c"]})
    assert r.summary.added == 1
    assert r.changes[0].path == "tags[2]"
    r = diff({"tags": ["a", "b"]}, {"tags": ["a"]})
    assert r.summary.removed == 1
    assert r.changes[0].path == "tags[1]"


def test_scalar_array_with_nulls_positional():
    r = diff({"a": [None, 1]}, {"a": [1, None]})
    assert r.summary.total == 2
    assert all(c.type is ChangeType.CHANGED for c in r.changes)


def test_non_unique_id_is_not_used_as_identity():
    before = [{"id": "X", "v": 1}, {"id": "X", "v": 2}]
    after = [{"id": "X", "v": 2}, {"id": "X", "v": 1}]
    assert find_identity_key(before, after) is None
    r = diff({"items": before}, {"items": after})
    assert r.positional_arrays == ["items"]


def test_identity_key_must_be_present_in_all_elements_on_both_sides():
    before = [{"id": "A"}, {"id": "B"}]
    after = [{"id": "A"}, {"name": "B"}]
    assert find_identity_key(before, after) is None


def test_identity_key_priority_order():
    before = [{"name": "n1", "code": "c1"}, {"name": "n2", "code": "c2"}]
    after = [{"name": "n2", "code": "c2"}, {"name": "n1", "code": "c1"}]
    assert find_identity_key(before, after) == "code"  # code comes before name


def test_configurable_identity_keys():
    before = {"rows": [{"sku": "A", "qty": 1}, {"sku": "B", "qty": 2}]}
    after = {"rows": [{"sku": "B", "qty": 2}, {"sku": "A", "qty": 1}]}
    assert diff(before, after).summary.total == 4  # default: positional
    r = diff_json(before, after, DiffOptions(identity_keys=("sku",)))
    assert r.summary.total == 0


def test_string_and_number_ids_do_not_collide():
    before = [{"id": 1}, {"id": "1"}]
    after = [{"id": "1"}, {"id": 1}]
    assert find_identity_key(before, after) == "id"
    r = diff({"x": before}, {"x": after})
    assert r.summary.total == 0


def test_mixed_arrays_fall_back_to_positional():
    result = match_arrays([{"id": 1}, "scalar"], [{"id": 1}, "scalar"])
    assert result.mode is MatchMode.POSITION


def test_nested_arrays_with_identity():
    before = {
        "locations": [
            {
                "location_id": "L1",
                "terminals": [{"id": "T1", "tid": "1"}, {"id": "T2", "tid": "2"}],
            },
            {"location_id": "L2", "terminals": [{"id": "T3", "tid": "3"}]},
        ]
    }
    after = {
        "locations": [
            {"location_id": "L2", "terminals": [{"id": "T3", "tid": "3"}]},
            {
                "location_id": "L1",
                "terminals": [{"id": "T2", "tid": "22"}, {"id": "T1", "tid": "1"}],
            },
        ]
    }
    r = diff(before, after)
    assert r.summary.total == 1
    c = r.changes[0]
    assert c.path == "locations[location_id=L1].terminals[id=T2].tid"
    assert c.display_path == "Location L1 / Terminal T2 / TID"
    assert (c.old_value, c.new_value) == ("2", "22")


def test_nested_array_in_positional_array():
    before = {"grid": [[1, 2], [3, 4]]}
    after = {"grid": [[1, 2], [3, 5]]}
    r = diff(before, after)
    assert r.summary.total == 1
    assert r.changes[0].path == "grid[1][1]"
    assert r.changes[0].note == POSITIONAL_NOTE


def test_identity_array_change_order_is_before_order_then_added():
    before = {"t": [{"id": "B", "v": 1}, {"id": "A", "v": 1}]}
    after = {"t": [{"id": "A", "v": 2}, {"id": "C", "v": 0}, {"id": "B", "v": 2}]}
    r = diff(before, after)
    assert [c.path for c in r.changes] == ["t[id=B].v", "t[id=A].v", "t[id=C]"]


def test_empty_array_to_populated_array():
    r = diff({"t": []}, {"t": [T1]})
    assert r.summary.added == 1
    assert r.changes[0].path == "t[id=T1]"
    assert r.positional_arrays == []

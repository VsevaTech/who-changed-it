"""Deterministic semantic diff of two JSON documents.

Rules
-----
* Object key order, whitespace and formatting are never changes.
* Arrays are matched semantically (see :mod:`app.services.array_matcher`); a reorder of
  reliably matched elements is not a change.
* Values are compared type-aware: ``"30"`` ≠ ``30``, ``true`` ≠ ``1``, ``null`` ≠ ``""``.
  Numbers compare by exact decimal value (``30`` == ``30.0``), never through ``float``.
* Sensitive values (by key name) are masked before they leave this module.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.diff import Change, ChangeType, DiffReport, MatchStrategy
from app.services.array_matcher import DEFAULT_IDENTITY_KEYS, match_arrays
from app.services.paths import (
    Segment,
    display_path,
    group_for,
    object_keys,
    raw_path,
)
from app.services.sensitive import contains_sensitive, mask_value, path_is_sensitive

POSITIONAL_NOTE = "Array matched by position"


def values_equal(a: Any, b: Any) -> bool:
    """Type-aware structural equality."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a is b
    if isinstance(a, int | Decimal) and isinstance(b, int | Decimal):
        return Decimal(a) == Decimal(b)
    if isinstance(a, int | Decimal) or isinstance(b, int | Decimal):
        return False
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(values_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        m = match_arrays(a, b)
        if m.added or m.removed:
            return False
        return all(values_equal(p.before, p.after) for p in m.pairs)
    return False


class DiffEngine:
    def __init__(self, identity_keys: tuple[str, ...] = DEFAULT_IDENTITY_KEYS):
        self.identity_keys = identity_keys

    def diff(self, before: Any, after: Any) -> DiffReport:
        changes: list[Change] = []
        notes: list[str] = []
        self._walk([], before, after, changes, notes)
        # Deterministic ordering: by raw path, then type.
        changes.sort(key=lambda c: (c.path, c.type))
        return DiffReport.from_changes(changes, sorted(set(notes)))

    # -- internals -------------------------------------------------------------------------

    def _walk(
        self,
        segments: list[Segment],
        before: Any,
        after: Any,
        changes: list[Change],
        notes: list[str],
        note: str | None = None,
    ) -> None:
        if isinstance(before, dict) and isinstance(after, dict):
            for key in sorted(before.keys() | after.keys()):
                seg = [*segments, Segment(key=key)]
                if key not in after:
                    changes.append(self._change(ChangeType.REMOVED, seg, before[key], None, note))
                elif key not in before:
                    changes.append(self._change(ChangeType.ADDED, seg, None, after[key], note))
                else:
                    self._walk(seg, before[key], after[key], changes, notes, note)
            return

        if isinstance(before, list) and isinstance(after, list):
            self._walk_arrays(segments, before, after, changes, notes, note)
            return

        if not values_equal(before, after):
            changes.append(self._change(ChangeType.CHANGED, segments, before, after, note))

    def _walk_arrays(
        self,
        segments: list[Segment],
        before: list[Any],
        after: list[Any],
        changes: list[Change],
        notes: list[str],
        parent_note: str | None = None,
    ) -> None:
        match = match_arrays(before, after, self.identity_keys)
        array_name = segments[-1].key if segments and segments[-1].key else None
        positional = match.strategy is MatchStrategy.POSITION
        # A positional note is inherited by everything below: if the element pairing is a
        # guess, every change inside it is only as reliable as that guess.
        note = POSITIONAL_NOTE if positional else parent_note
        if positional and (match.pairs or match.added or match.removed):
            notes.append(f"{raw_path(segments)}: {POSITIONAL_NOTE}")

        def seg_for(identity: str | None, index: int | None) -> Segment:
            return Segment(array=array_name, identity=identity, index=index)

        for pair in match.pairs:
            if match.strategy is MatchStrategy.VALUE:
                continue  # same scalar present on both sides — nothing to compare
            idx = pair.after_index if pair.after_index is not None else pair.before_index
            child = [*segments, seg_for(pair.identity if not positional else None, idx)]
            self._walk(child, pair.before, pair.after, changes, notes, note)

        for pair in match.removed:
            child = [
                *segments,
                seg_for(pair.identity if not positional else None, pair.before_index),
            ]
            changes.append(self._change(ChangeType.REMOVED, child, pair.before, None, note))

        for pair in match.added:
            child = [
                *segments,
                seg_for(pair.identity if not positional else None, pair.after_index),
            ]
            changes.append(self._change(ChangeType.ADDED, child, None, pair.after, note))

    def _change(
        self,
        kind: ChangeType,
        segments: list[Segment],
        old: Any,
        new: Any,
        note: str | None,
    ) -> Change:
        keys = object_keys(segments)
        sensitive_path = path_is_sensitive(keys)
        sensitive = sensitive_path or contains_sensitive(old) or contains_sensitive(new)
        identity = next((s.identity for s in reversed(segments) if s.identity), None)
        container = isinstance(old, dict | list) or isinstance(new, dict | list)
        return Change(
            type=kind,
            path=raw_path(segments),
            display_path=display_path(segments),
            group=group_for(segments, container=container),
            old_value=mask_value(old, force=sensitive_path) if old is not None else None,
            new_value=mask_value(new, force=sensitive_path) if new is not None else None,
            identity=identity,
            sensitive=sensitive,
            note=note,
        )


def semantic_diff(
    before: Any, after: Any, identity_keys: tuple[str, ...] = DEFAULT_IDENTITY_KEYS
) -> DiffReport:
    return DiffEngine(identity_keys).diff(before, after)

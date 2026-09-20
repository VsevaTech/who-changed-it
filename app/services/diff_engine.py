"""Deterministic semantic diff of two parsed JSON documents."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app import settings
from app.models.diff import Change, ChangeType, DiffResult, Identity, MatchMode, Summary
from app.services.array_matcher import match_arrays
from app.services.humanize import (
    IdentitySegment,
    IndexSegment,
    KeySegment,
    Segment,
    display_path,
    group_for,
    key_chain,
    raw_path,
)
from app.services.sensitive import SensitiveDetector
from app.services.values import values_equal

POSITIONAL_NOTE = "Array matched by position"


@dataclass(frozen=True)
class DiffOptions:
    identity_keys: Sequence[str] = settings.DEFAULT_IDENTITY_KEYS
    sensitive_keys: Sequence[str] = settings.DEFAULT_SENSITIVE_KEYS
    groups: dict[str, str] = field(default_factory=lambda: dict(settings.DEFAULT_GROUPS))


class DiffEngine:
    def __init__(self, options: DiffOptions | None = None) -> None:
        self.options = options or DiffOptions()
        self._detector = SensitiveDetector(self.options.sensitive_keys)

    # -- public API -------------------------------------------------------------------

    def diff(self, before: Any, after: Any) -> DiffResult:
        changes: list[Change] = []
        positional: list[str] = []
        self._walk(before, after, [], changes, positional, None, None)
        summary = Summary(
            total=len(changes),
            added=sum(1 for c in changes if c.type is ChangeType.ADDED),
            removed=sum(1 for c in changes if c.type is ChangeType.REMOVED),
            changed=sum(1 for c in changes if c.type is ChangeType.CHANGED),
        )
        return DiffResult(summary=summary, changes=changes, positional_arrays=positional)

    # -- internals --------------------------------------------------------------------

    def _emit(
        self,
        changes: list[Change],
        ctype: ChangeType,
        segments: list[Segment],
        old: Any,
        new: Any,
        identity: Identity | None,
        match_mode: MatchMode | None,
    ) -> None:
        sensitive = self._detector.path_is_sensitive(key_chain(segments))
        if sensitive:
            old = self._detector.mask(old)
            new = self._detector.mask(new)
        else:
            old, hit_old = self._detector.mask_nested(old)
            new, hit_new = self._detector.mask_nested(new)
            sensitive = hit_old or hit_new
        changes.append(
            Change(
                type=ctype,
                path=raw_path(segments),
                display_path=display_path(segments),
                group=group_for(segments, self.options.groups),
                old_value=old,
                new_value=new,
                identity=identity,
                sensitive=sensitive,
                match_mode=match_mode,
                note=POSITIONAL_NOTE if match_mode is MatchMode.POSITION else None,
            )
        )

    def _walk(
        self,
        before: Any,
        after: Any,
        segments: list[Segment],
        changes: list[Change],
        positional: list[str],
        identity: Identity | None,
        match_mode: MatchMode | None,
    ) -> None:
        if isinstance(before, dict) and isinstance(after, dict):
            self._walk_dict(before, after, segments, changes, positional, identity, match_mode)
        elif isinstance(before, list) and isinstance(after, list):
            self._walk_list(before, after, segments, changes, positional, identity)
        elif not values_equal(before, after):
            self._emit(changes, ChangeType.CHANGED, segments, before, after, identity, match_mode)

    def _walk_dict(
        self,
        before: dict[str, Any],
        after: dict[str, Any],
        segments: list[Segment],
        changes: list[Change],
        positional: list[str],
        identity: Identity | None,
        match_mode: MatchMode | None,
    ) -> None:
        # Key order never matters; iterate deterministically in sorted order.
        for key in sorted(before.keys() | after.keys()):
            path = [*segments, KeySegment(key)]
            if key not in after:
                self._emit(
                    changes, ChangeType.REMOVED, path, before[key], None, identity, match_mode
                )
            elif key not in before:
                self._emit(changes, ChangeType.ADDED, path, None, after[key], identity, match_mode)
            else:
                self._walk(before[key], after[key], path, changes, positional, identity, match_mode)

    def _walk_list(
        self,
        before: list[Any],
        after: list[Any],
        segments: list[Segment],
        changes: list[Change],
        positional: list[str],
        identity: Identity | None,
    ) -> None:
        if values_equal(before, after):
            return
        parent_key = segments[-1].key if segments and isinstance(segments[-1], KeySegment) else None
        result = match_arrays(before, after, self.options.identity_keys)

        if result.mode is MatchMode.POSITION:
            positional.append(raw_path(segments))

        for ident_value, b, a in result.pairs:
            if result.mode is MatchMode.IDENTITY:
                seg: Segment = IdentitySegment(result.identity_key, ident_value, parent_key)
                el_identity = Identity(key=result.identity_key, value=ident_value)
            else:
                seg = IndexSegment(ident_value, parent_key)
                el_identity = identity
            path = [*segments, seg]

            if b is None and a is None:
                continue  # cannot happen, defensive
            if a is None and (result.mode is MatchMode.IDENTITY or ident_value >= len(after)):
                self._emit(changes, ChangeType.REMOVED, path, b, None, el_identity, result.mode)
            elif b is None and (result.mode is MatchMode.IDENTITY or ident_value >= len(before)):
                self._emit(changes, ChangeType.ADDED, path, None, a, el_identity, result.mode)
            else:
                self._walk(b, a, path, changes, positional, el_identity, result.mode)


def diff_json(before: Any, after: Any, options: DiffOptions | None = None) -> DiffResult:
    return DiffEngine(options).diff(before, after)

"""Pydantic models describing the diff result."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class MatchMode(StrEnum):
    IDENTITY = "identity"
    POSITION = "position"


class Identity(BaseModel):
    """How an array element was identified (e.g. `id=T2`)."""

    key: str
    value: Any


class Change(BaseModel):
    type: ChangeType
    path: str = Field(description="Raw JSON path, e.g. terminals[id=T2].tid")
    display_path: str = Field(description="Human-readable path, e.g. Terminal T2 / TID")
    group: str
    old_value: Any = None
    new_value: Any = None
    identity: Identity | None = None
    sensitive: bool = False
    match_mode: MatchMode | None = Field(
        default=None,
        description="Set when the change lives inside an array: how elements were matched.",
    )
    note: str | None = Field(
        default=None,
        description="Extra context for humans, e.g. 'Array matched by position'.",
    )


class Summary(BaseModel):
    total: int = 0
    added: int = 0
    removed: int = 0
    changed: int = 0

    @property
    def is_equivalent(self) -> bool:
        return self.total == 0


class DiffResult(BaseModel):
    summary: Summary
    changes: list[Change]
    positional_arrays: list[str] = Field(
        default_factory=list,
        description="Raw paths of arrays that had to be compared by position.",
    )

    @property
    def groups(self) -> list[tuple[str, list[Change]]]:
        """Changes grouped by section. Well-known sections first, then alphabetical."""
        buckets: dict[str, list[Change]] = {}
        for change in self.changes:
            buckets.setdefault(change.group, []).append(change)

        def rank(group: str) -> tuple[int, str]:
            if group in GROUP_ORDER:
                return (GROUP_ORDER.index(group), group)
            if group == "Other":
                return (len(GROUP_ORDER) + 1, group)
            return (len(GROUP_ORDER), group)

        return [(g, buckets[g]) for g in sorted(buckets, key=rank)]


GROUP_ORDER: tuple[str, ...] = ("Company", "Payments", "Terminals", "Features", "Billing")

"""Pydantic models describing a semantic diff report."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

JsonValue = None | bool | int | Decimal | str | list[Any] | dict[str, Any]


class ChangeType(StrEnum):
    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


class MatchStrategy(StrEnum):
    """How the elements of an array were paired between before/after."""

    IDENTITY = "identity"  # objects matched by a unique identity key
    VALUE = "value"  # scalars matched by their own value
    POSITION = "position"  # fallback: index-by-index comparison


class Change(BaseModel):
    type: ChangeType
    path: str = Field(description="Raw JSON path, e.g. terminals[id=T2].tid")
    display_path: str = Field(description="Humanized path, e.g. Terminal T2 / TID")
    group: str = Field(description="Top-level section the change belongs to")
    old_value: Any = None
    new_value: Any = None
    identity: str | None = Field(
        default=None,
        description="Identity of the array element this change belongs to, e.g. id=T2",
    )
    sensitive: bool = False
    note: str | None = Field(
        default=None,
        description="Extra context, e.g. 'Array matched by position'",
    )

    model_config = {"arbitrary_types_allowed": True}


class Summary(BaseModel):
    total: int = 0
    added: int = 0
    removed: int = 0
    changed: int = 0


class DiffReport(BaseModel):
    summary: Summary
    changes: list[Change]
    notes: list[str] = Field(
        default_factory=list,
        description="Report-level notes, e.g. arrays that fell back to positional matching",
    )

    @classmethod
    def from_changes(cls, changes: list[Change], notes: list[str] | None = None) -> DiffReport:
        summary = Summary(
            total=len(changes),
            added=sum(1 for c in changes if c.type is ChangeType.ADDED),
            removed=sum(1 for c in changes if c.type is ChangeType.REMOVED),
            changed=sum(1 for c in changes if c.type is ChangeType.CHANGED),
        )
        return cls(summary=summary, changes=changes, notes=notes or [])

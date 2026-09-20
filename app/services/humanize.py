"""Turn raw JSON paths into something a support engineer can read."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app import settings
from app.services.values import render_value

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


@dataclass(frozen=True)
class KeySegment:
    key: str

    def raw(self, first: bool) -> str:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", self.key):
            return self.key if first else f".{self.key}"
        return f"[{json.dumps(self.key, ensure_ascii=False)}]"


@dataclass(frozen=True)
class IdentitySegment:
    key: str
    value: Any
    parent_key: str | None

    def raw(self, first: bool) -> str:
        return f"[{self.key}={render_value(self.value)}]"


@dataclass(frozen=True)
class IndexSegment:
    index: int
    parent_key: str | None

    def raw(self, first: bool) -> str:
        return f"[{self.index}]"


Segment = KeySegment | IdentitySegment | IndexSegment


def raw_path(segments: list[Segment]) -> str:
    if not segments:
        return "$"
    return "".join(seg.raw(i == 0) for i, seg in enumerate(segments))


def humanize_key(key: str) -> str:
    """`payment_settings` -> `Payment settings`, `terminalId` -> `Terminal ID`."""
    words = _CAMEL_RE.sub(" ", key).replace("_", " ").replace("-", " ").split()
    if not words:
        return key
    out: list[str] = []
    for i, w in enumerate(words):
        lw = w.lower()
        if lw in settings.ACRONYMS:
            out.append(lw.upper())
        elif i == 0:
            out.append(lw.capitalize())
        else:
            out.append(lw)
    return " ".join(out)


def singularize(word: str) -> str:
    lw = word.lower()
    if lw.endswith("ies") and len(lw) > 3:
        return word[:-3] + "y"
    if lw.endswith(("ss", "us", "is")):
        return word
    if lw.endswith("es") and lw[-3:-2] in ("x", "s", "z") or lw.endswith(("ches", "shes")):
        return word[:-2]
    if lw.endswith("s") and len(lw) > 1:
        return word[:-1]
    return word


def display_path(segments: list[Segment]) -> str:
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, KeySegment):
            parts.append(humanize_key(seg.key))
        elif isinstance(seg, IdentitySegment):
            noun = humanize_key(singularize(seg.parent_key)) if seg.parent_key else "Item"
            label = f"{noun} {render_value(seg.value)}"
            if parts and seg.parent_key is not None:
                parts[-1] = label  # replace "Terminals" with "Terminal T2"
            else:
                parts.append(label)
        elif isinstance(seg, IndexSegment):
            noun = humanize_key(singularize(seg.parent_key)) if seg.parent_key else "Item"
            label = f"{noun} #{seg.index + 1}"
            if parts and seg.parent_key is not None:
                parts[-1] = label
            else:
                parts.append(label)
    return " / ".join(parts) if parts else "Root"


def group_for(segments: list[Segment], groups: dict[str, str] = settings.DEFAULT_GROUPS) -> str:
    if not segments or not isinstance(segments[0], KeySegment):
        return "Other"
    root = segments[0].key
    if root in groups:
        return groups[root]
    normalized = root.lower().replace("-", "_")
    if normalized in groups:
        return groups[normalized]
    return humanize_key(root)


def key_chain(segments: list[Segment]) -> list[str]:
    """Only the object keys on the path — used for sensitive detection."""
    return [seg.key for seg in segments if isinstance(seg, KeySegment)]

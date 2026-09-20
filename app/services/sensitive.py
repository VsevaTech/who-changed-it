"""Detection and masking of sensitive values.

A value is sensitive when any *key* on its path (not the value itself) contains one of
the configured fragments after normalization. Masking happens before a `Change` object is
created, so raw secrets never reach templates, logs, exports or the browser.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

from app import settings

_NORMALIZE_RE = re.compile(r"[^a-z0-9]")


def normalize_key(key: str) -> str:
    return _NORMALIZE_RE.sub("", key.lower())


class SensitiveDetector:
    def __init__(self, fragments: Iterable[str] = settings.DEFAULT_SENSITIVE_KEYS) -> None:
        self._fragments = tuple(sorted({normalize_key(f) for f in fragments if f}))

    def is_sensitive_key(self, key: str) -> bool:
        norm = normalize_key(key)
        return any(frag in norm for frag in self._fragments)

    def path_is_sensitive(self, keys: Sequence[str]) -> bool:
        return any(self.is_sensitive_key(k) for k in keys)

    @staticmethod
    def mask(value: Any) -> Any:
        """Replace a value with the mask. `None` stays `None` so ADDED/REMOVED remain visible."""
        if value is None:
            return None
        return settings.MASK

    def mask_nested(self, value: Any) -> tuple[Any, bool]:
        """Walk a composite value and mask every sensitive key inside it.

        Needed when a whole object is added/removed/replaced: the change is reported at the
        parent path, but secrets nested inside must still never leave the engine.
        Returns (masked_copy, anything_was_masked).
        """
        if isinstance(value, dict):
            out: dict[str, Any] = {}
            hit = False
            for key, inner in value.items():
                if self.is_sensitive_key(key):
                    out[key] = self.mask(inner)
                    hit = hit or inner is not None
                else:
                    out[key], inner_hit = self.mask_nested(inner)
                    hit = hit or inner_hit
            return out, hit
        if isinstance(value, list):
            items = [self.mask_nested(v) for v in value]
            return [v for v, _ in items], any(h for _, h in items)
        return value, False

"""Detection and masking of potentially sensitive values.

Detection is based purely on key names along the JSON path — the values themselves are
never inspected, logged or echoed. Masking is applied *before* a value reaches templates,
exports or any other output channel.
"""

from __future__ import annotations

import re
from typing import Any

MASK = "••••••"

# Single tokens that mark a key as sensitive wherever they occur (``access_token``,
# ``dbPassword``, ``SECRET``).
SENSITIVE_TOKENS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "authorization",
        "apikey",
        "credential",
        "credentials",
        "cvv",
        "cvc",
    }
)

# Two-token compounds; ``key`` alone must stay usable as an identity key.
SENSITIVE_COMPOUNDS: frozenset[str] = frozenset(
    {
        "api_key",
        "private_key",
        "secret_key",
        "signing_key",
        "encryption_key",
        "client_secret",
        "access_token",
        "refresh_token",
        "auth_key",
        "pin_code",
        "card_pin",
        "pin_block",
    }
)

_CAMEL_RE = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _tokens(key: str) -> list[str]:
    spaced = _CAMEL_RE.sub("_", key)
    return [t for t in re.split(r"[^a-zA-Z0-9]+", spaced.lower()) if t]


def is_sensitive_key(key: str) -> bool:
    tokens = _tokens(key)
    if any(t in SENSITIVE_TOKENS for t in tokens):
        return True
    return any(f"{a}_{b}" in SENSITIVE_COMPOUNDS for a, b in zip(tokens, tokens[1:], strict=False))


def path_is_sensitive(keys: list[str]) -> bool:
    """*keys* are the object keys along the path (array identities excluded)."""
    return any(is_sensitive_key(k) for k in keys)


def mask_value(value: Any, *, force: bool = False) -> Any:
    """Return a copy of *value* with sensitive parts replaced by :data:`MASK`.

    With ``force=True`` the whole value is masked (used when the path itself is sensitive).
    Otherwise nested dict keys are inspected so that e.g. an added object carrying a
    ``client_secret`` is exported with that field hidden.
    """
    if force:
        return MASK
    if isinstance(value, dict):
        return {k: (MASK if is_sensitive_key(k) else mask_value(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(v) for v in value]
    return value


def contains_sensitive(value: Any) -> bool:
    if isinstance(value, dict):
        return any(is_sensitive_key(k) or contains_sensitive(v) for k, v in value.items())
    if isinstance(value, list):
        return any(contains_sensitive(v) for v in value)
    return False

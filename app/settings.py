"""Static, deterministic configuration for the diff engine.

Everything here can be overridden per call (see `DiffOptions`), but the defaults
are deliberately conservative: no guessing, no aggressive normalization.
"""

from __future__ import annotations

# Maximum accepted size of a single JSON document (bytes).
MAX_JSON_BYTES = 5 * 1024 * 1024

# Maximum nesting depth we are willing to walk. Protects against pathological input.
MAX_DEPTH = 200

# Candidate identity keys for arrays of objects, in priority order.
# A key is only used when it is present in every element of both arrays,
# holds a scalar value, and is unique within each array.
DEFAULT_IDENTITY_KEYS: tuple[str, ...] = (
    "id",
    "uuid",
    "code",
    "key",
    "name",
    "tid",
    "terminal_id",
    "company_id",
    "location_id",
)

# Key fragments that mark a value as sensitive. Matching is done on a normalized
# key (lower-case, `-` and `_` removed) so `client_secret`, `clientSecret` and
# `CLIENT-SECRET` are all caught.
DEFAULT_SENSITIVE_KEYS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "access_token",
    "refresh_token",
    "authorization",
    "api_key",
    "apikey",
    "private_key",
    "client_secret",
    "credential",
)

MASK = "••••••"

# Root-level JSON sections mapped to human-readable group titles.
# Unknown sections fall back to a humanized version of the section name.
DEFAULT_GROUPS: dict[str, str] = {
    "company": "Company",
    "merchant": "Company",
    "organization": "Company",
    "payments": "Payments",
    "payment": "Payments",
    "payment_settings": "Payments",
    "terminals": "Terminals",
    "terminal": "Terminals",
    "features": "Features",
    "feature_flags": "Features",
    "billing": "Billing",
    "invoicing": "Billing",
}

# Tokens rendered upper-case in display paths.
ACRONYMS: frozenset[str] = frozenset(
    {"id", "tid", "mid", "uuid", "url", "uri", "api", "iban", "bic", "vat", "trn", "pos", "kyc"}
)

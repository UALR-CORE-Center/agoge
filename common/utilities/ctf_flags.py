"""
The single definition of CTF flag derivation. The planter, the event creator, the
reveal route, and the submission checker import these functions; none reimplements them.

Flag values are never persisted. Firestore holds only flag_digest(value); the value is
re-derived from the Secret Manager seed whenever it is needed.
"""
import hashlib
import hmac
import re
from typing import Optional

DIGEST_HEX_LENGTH = 20


def derive_flag_value(seed: str, workout_id: str, flag_id: str,
                      seed_version: int, prefix: str = "agoge") -> str:
    """
    Returns '<prefix>{<flag_id>_<digest>}' where digest is the first 20 hex
    characters of HMAC-SHA256(seed, f"{seed_version}:{workout_id}:{flag_id}").
    """
    message = f"{seed_version}:{workout_id}:{flag_id}"
    digest = hmac.new(seed.encode(), message.encode(), hashlib.sha256).hexdigest()
    return f"{prefix}{{{flag_id}_{digest[:DIGEST_HEX_LENGTH]}}}"


def normalize_flag(submitted: str) -> str:
    """Strip surrounding whitespace, then lowercase. Nothing else."""
    return submitted.strip().lower()


def flag_digest(value: str) -> str:
    """SHA-256 hex of normalize_flag(value). The only form ever persisted."""
    return hashlib.sha256(normalize_flag(value).encode()).hexdigest()


def flags_match(submitted: str, expected_digest: str) -> bool:
    """hmac.compare_digest(flag_digest(submitted), expected_digest)."""
    # Constant-time comparison; never `==`, which leaks the matching prefix length.
    return hmac.compare_digest(flag_digest(submitted), expected_digest)


def parse_flag_id(submitted: str, prefix: str) -> Optional[str]:
    r"""Returns <flag_id> if normalize_flag(submitted) matches
    ^<prefix>\{([a-z0-9-]+)_[0-9a-f]{20}\}$, else None. Used for rate-limit
    bucketing and attempt counting only — never as proof of correctness."""
    # The submission is lowercased, so the prefix must be too or a mixed-case prefix never matches.
    pattern = rf"^{re.escape(prefix.lower())}\{{([a-z0-9-]+)_[0-9a-f]{{{DIGEST_HEX_LENGTH}}}\}}$"
    match = re.fullmatch(pattern, normalize_flag(submitted))
    return match.group(1) if match else None

"""Normalization shared by risk and Teams destination route keys."""
import re


ROUTE_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")


def normalize_route_key(value: str) -> str:
    """Return the canonical route key or raise a validation-friendly error."""
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    if not normalized or not ROUTE_KEY_PATTERN.fullmatch(normalized):
        raise ValueError(
            "route key must contain only letters, numbers, hyphens, or underscores"
        )
    return normalized

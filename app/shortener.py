"""Validation, expiry, and base62 helpers used by the application."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re

import validators

BASE62_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
ALIAS_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
EXPIRY_OPTIONS: dict[str, timedelta | None] = {
    "never": None,
    "1 hour": timedelta(hours=1),
    "1 day": timedelta(days=1),
    "7 days": timedelta(days=7),
}


def encode_base62(number: int) -> str:
    """Encode a non-negative integer as a compact base62 string."""
    if number < 0:
        raise ValueError("Base62 encoding only accepts non-negative integers.")
    if number == 0:
        return BASE62_ALPHABET[0]

    characters: list[str] = []
    while number:
        number, remainder = divmod(number, 62)
        characters.append(BASE62_ALPHABET[remainder])
    return "".join(reversed(characters))


def decode_base62(value: str) -> int:
    """Decode a base62 string into an integer."""
    if not value:
        raise ValueError("Base62 value cannot be empty.")

    number = 0
    for character in value:
        try:
            digit = BASE62_ALPHABET.index(character)
        except ValueError as error:
            raise ValueError(f"Invalid base62 character: {character!r}") from error
        number = number * 62 + digit
    return number


def validate_url(url: str) -> str:
    """Return a cleaned HTTP(S) URL or raise a user-friendly error."""
    cleaned_url = url.strip()
    if not cleaned_url:
        raise ValueError("Please enter a URL.")
    if not validators.url(cleaned_url):
        raise ValueError("Enter a valid URL beginning with http:// or https://.")
    return cleaned_url


def validate_alias(alias: str | None) -> str | None:
    """Validate an optional URL-safe custom alias."""
    if alias is None or not alias.strip():
        return None
    cleaned_alias = alias.strip()
    if not ALIAS_PATTERN.fullmatch(cleaned_alias):
        raise ValueError(
            "Alias must be 3-32 characters using letters, numbers, hyphens, or underscores."
        )
    return cleaned_alias


def calculate_expiry(expiry_option: str) -> datetime | None:
    """Convert an expiry label from the UI/API to a UTC timestamp."""
    if expiry_option not in EXPIRY_OPTIONS:
        raise ValueError("Expiry must be never, 1 hour, 1 day, or 7 days.")
    duration = EXPIRY_OPTIONS[expiry_option]
    return None if duration is None else datetime.now(timezone.utc) + duration


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def timestamp_to_text(value: datetime | None) -> str | None:
    """Serialize a UTC timestamp for storage in SQLite."""
    return None if value is None else value.isoformat()


def text_to_timestamp(value: str | None) -> datetime | None:
    """Deserialize a SQLite timestamp, keeping it timezone-aware."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

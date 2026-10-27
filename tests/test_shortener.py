"""Unit tests for link code and alias validation helpers."""

import pytest

from app.shortener import decode_base62, encode_base62, validate_alias


@pytest.mark.parametrize("number", [0, 1, 61, 62, 12345, 987654321])
def test_base62_round_trip(number: int) -> None:
    """Every encoded number should decode to its original value."""
    assert decode_base62(encode_base62(number)) == number


def test_base62_known_values() -> None:
    """Base62 uses digits, lowercase letters, then uppercase letters."""
    assert encode_base62(61) == "Z"
    assert encode_base62(62) == "10"


@pytest.mark.parametrize("alias", ["college2026", "my-link", "my_link", "A1B2"])
def test_valid_aliases(alias: str) -> None:
    """URL-safe aliases are accepted."""
    assert validate_alias(alias) == alias


@pytest.mark.parametrize("alias", ["ab", "has spaces", "bad/slash", "!invalid", "x" * 33])
def test_invalid_aliases(alias: str) -> None:
    """Aliases outside the documented pattern are rejected."""
    with pytest.raises(ValueError, match="Alias must"):
        validate_alias(alias)


def test_blank_alias_is_optional() -> None:
    """A blank alias means an auto-generated code is requested."""
    assert validate_alias("   ") is None

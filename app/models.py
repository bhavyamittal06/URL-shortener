"""Pydantic schemas for the URL shortener API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


ExpiryOption = Literal["never", "1 hour", "1 day", "7 days"]


class ShortenRequest(BaseModel):
    """Payload accepted when creating a short link."""

    url: str = Field(min_length=1, max_length=2048)
    alias: Optional[str] = Field(default=None, max_length=32)
    expiry: ExpiryOption = "never"


class ShortenResponse(BaseModel):
    """Short-link details returned after creating or finding a link."""

    short_code: str
    short_url: str


class LinkRecord(BaseModel):
    """A link record shown in the history view."""

    id: int
    short_code: str
    original_url: str
    click_count: int
    created_at: str
    expires_at: Optional[str]
    last_accessed_at: Optional[str]


class LinkStats(BaseModel):
    """Analytics details for one short link."""

    short_code: str
    original_url: str
    click_count: int
    created_at: str
    expires_at: Optional[str]
    last_accessed_at: Optional[str]

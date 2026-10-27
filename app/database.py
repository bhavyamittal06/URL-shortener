"""SQLite persistence layer with parameterized statements only."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator
from uuid import uuid4

from app.shortener import (
    calculate_expiry,
    encode_base62,
    text_to_timestamp,
    timestamp_to_text,
    utc_now,
)

DATABASE_PATH = Path(__file__).resolve().parent.parent / "url_shortener.db"


class AliasAlreadyExistsError(ValueError):
    """Raised when a requested custom alias is already in use."""


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a short-lived SQLite connection suitable for worker threads."""
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create the links table and indexes if they do not yet exist."""
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT NOT NULL UNIQUE,
                original_url TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL,
                expires_at TEXT,
                click_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_links_short_code ON links(short_code)"
        )


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a database row to JSON-safe API data."""
    return dict(row)


def create_or_get_link(
    original_url: str, alias: str | None, expiry_option: str
) -> tuple[dict[str, Any], bool]:
    """Create a link, or return its existing record for duplicate URLs.

    The auto-generated code is derived from the SQLite auto-increment ID. A
    transaction serializes that two-step insert/update operation.
    """
    created_at = timestamp_to_text(utc_now())
    expires_at = timestamp_to_text(calculate_expiry(expiry_option))

    with get_connection() as connection:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            "SELECT * FROM links WHERE original_url = ?", (original_url,)
        ).fetchone()
        if existing:
            return _row_to_dict(existing), False

        try:
            if alias:
                cursor = connection.execute(
                    """
                    INSERT INTO links (short_code, original_url, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (alias, original_url, created_at, expires_at),
                )
            else:
                pending_code = f"pending-{uuid4()}"
                cursor = connection.execute(
                    """
                    INSERT INTO links (short_code, original_url, created_at, expires_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (pending_code, original_url, created_at, expires_at),
                )
                short_code = encode_base62(cursor.lastrowid)
                connection.execute(
                    "UPDATE links SET short_code = ? WHERE id = ?",
                    (short_code, cursor.lastrowid),
                )
        except sqlite3.IntegrityError as error:
            if alias:
                raise AliasAlreadyExistsError("That custom alias is already taken.") from error
            raise

        record = connection.execute(
            "SELECT * FROM links WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        if record is None:
            raise RuntimeError("Link creation did not return a database record.")
        return _row_to_dict(record), True


def get_link(short_code: str) -> dict[str, Any] | None:
    """Return one link by its short code, if it exists."""
    with get_connection() as connection:
        row = connection.execute(
            "SELECT * FROM links WHERE short_code = ?", (short_code,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_links() -> list[dict[str, Any]]:
    """Return all links from newest to oldest."""
    with get_connection() as connection:
        rows = connection.execute("SELECT * FROM links ORDER BY id DESC").fetchall()
    return [_row_to_dict(row) for row in rows]


def record_click(short_code: str) -> None:
    """Increase click analytics after a successful redirect lookup."""
    with get_connection() as connection:
        connection.execute(
            """
            UPDATE links
            SET click_count = click_count + 1, last_accessed_at = ?
            WHERE short_code = ?
            """,
            (timestamp_to_text(utc_now()), short_code),
        )


def is_expired(link: dict[str, Any]) -> bool:
    """Determine whether a stored link has passed its expiry timestamp."""
    expires_at = text_to_timestamp(link["expires_at"])
    return expires_at is not None and expires_at <= utc_now()


def delete_link(short_code: str) -> bool:
    """Delete a link and report whether a row was removed."""
    with get_connection() as connection:
        cursor = connection.execute("DELETE FROM links WHERE short_code = ?", (short_code,))
    return cursor.rowcount > 0

"""FastAPI routes for creating, listing, redirecting, and deleting links."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.database import (
    AliasAlreadyExistsError,
    create_or_get_link,
    delete_link,
    get_link,
    initialize_database,
    is_expired,
    list_links,
    record_click,
)
from app.models import LinkRecord, LinkStats, ShortenRequest, ShortenResponse
from app.shortener import validate_alias, validate_url

APP_HOST = "127.0.0.1"
APP_PORT = 8000
BASE_URL = f"http://{APP_HOST}:{APP_PORT}"

app = FastAPI(title="College URL Shortener", version="1.0.0")


@app.on_event("startup")
def start_database() -> None:
    """Ensure the local database exists before accepting requests."""
    initialize_database()


@app.post("/api/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten_url(payload: ShortenRequest, response: Response) -> ShortenResponse:
    """Create a short link or return an existing link for the same URL."""
    try:
        url = validate_url(payload.url)
        alias = validate_alias(payload.alias)
        record, created = create_or_get_link(url, alias, payload.expiry)
    except AliasAlreadyExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    if not created:
        response.status_code = status.HTTP_200_OK
    return ShortenResponse(
        short_code=record["short_code"],
        short_url=f"{BASE_URL}/{record['short_code']}",
    )


@app.get("/api/links", response_model=list[LinkRecord])
def get_all_links() -> list[dict[str, object]]:
    """List saved links and their analytics for the GUI history table."""
    return list_links()


@app.get("/api/stats/{short_code}", response_model=LinkStats)
def get_stats(short_code: str) -> dict[str, object]:
    """Return analytics for one short code."""
    link = get_link(short_code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found.")
    return link


@app.delete("/api/links/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
def remove_link(short_code: str) -> Response:
    """Delete a short link from history."""
    if not delete_link(short_code):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/{short_code}")
def redirect_short_url(short_code: str) -> Response:
    """Redirect a valid short code and record its successful click."""
    link = get_link(short_code)
    if link is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Short link not found.")
    if is_expired(link):
        return HTMLResponse(
            "<h1>410 - Link Expired</h1><p>This short link is no longer available.</p>",
            status_code=status.HTTP_410_GONE,
        )
    record_click(short_code)
    return RedirectResponse(url=link["original_url"], status_code=status.HTTP_307_TEMPORARY_REDIRECT)

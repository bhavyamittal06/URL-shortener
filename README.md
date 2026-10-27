# URL Shortener Desktop Project

A college-ready Python URL shortener with a polished desktop interface. The app launches a local FastAPI service in the background and uses SQLite to persist short links, expiry dates, and click analytics.

## Features

- Create compact base62 short codes from SQLite auto-increment IDs.
- Optional custom aliases, validated as URL-safe and checked for duplicates.
- Optional expiry: never, one hour, one day, or seven days.
- Browser redirects using HTTP 307 and a clear HTTP 410 expired-link page.
- Duplicate long URLs return their existing short link.
- History table with search, refresh, deletion, click count, dates, and expiry.
- Copy, open-in-browser, QR-code preview, and dark/light mode controls.
- Responsive interface: API work always runs in background worker threads.

## Requirements

- Python 3.10 or newer.
- A desktop environment capable of running Tkinter (included with most Python installers).

## Setup and run

Open a terminal in this `url_shortener` folder, then run:

```bash
python3.10 -m venv .venv  # use any installed Python 3.10+ command
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
python main.py
```

The first run creates `url_shortener.db` automatically. The desktop window starts the local API at `http://127.0.0.1:8000` in a background thread.

On this Mac, use `python3.13 -m venv .venv`. If CustomTkinter cannot start on a particular operating-system build, the project automatically uses its included Tkinter fallback.

To run the unit tests:

```bash
pytest
```

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/shorten` | Create a link from `{ "url", "alias"?, "expiry"? }` |
| `GET` | `/api/links` | List all saved links |
| `GET` | `/api/stats/{short_code}` | Read one link's analytics |
| `DELETE` | `/api/links/{short_code}` | Delete a link |
| `GET` | `/{short_code}` | Redirect to the original URL or return 410 if expired |

Example request:

```bash
curl -X POST http://localhost:8000/api/shorten \\
  -H "Content-Type: application/json" \\
  -d '{"url":"https://www.example.com","alias":"college-demo","expiry":"1 day"}'
```

## Architecture

```text
Desktop GUI (CustomTkinter, Tkinter fallback)
       |  requests in worker threads
       v
FastAPI + Uvicorn (background daemon thread, port 8000)
       |  parameterized SQL via sqlite3
       v
SQLite database (links, analytics, expiry information)
       |
       +--> Browser receives HTTP 307 redirect / HTTP 410 expiry page
```

## Screenshots

Add screenshots here after running the application for your project report. Useful captures are the main form with a generated QR code and the populated history table.

## Future improvements

- Add user accounts and per-user dashboards.
- Deploy the FastAPI service with a public domain.
- Support custom branded domains and QR-code downloads.
- Add rate limiting, link editing, and richer analytics charts.

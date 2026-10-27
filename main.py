"""Launch the FastAPI server in the background and open the desktop GUI."""

from __future__ import annotations

import threading

import uvicorn

from app.api import APP_HOST, APP_PORT, app
from app.database import initialize_database
from gui.app_window import URLShortenerApp


def start_api_server() -> None:
    """Run Uvicorn without blocking the GUI event loop."""
    config = uvicorn.Config(app, host=APP_HOST, port=APP_PORT, log_level="warning")
    server = uvicorn.Server(config)
    server.run()


def main() -> None:
    """Initialize storage, start the local API thread, and show the window."""
    initialize_database()
    threading.Thread(target=start_api_server, daemon=True, name="fastapi-server").start()
    URLShortenerApp().run()


if __name__ == "__main__":
    main()

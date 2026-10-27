"""Responsive desktop GUI for demonstrating the URL shortener."""

from __future__ import annotations

from io import BytesIO
import threading
import webbrowser
from typing import Any, Callable, TypeVar

try:
    import customtkinter as ctk

    HAS_CUSTOMTKINTER = True
except Exception:  # pragma: no cover - depends on optional GUI package and OS support
    # Some macOS builds can import CustomTkinter but fail while detecting the
    # system appearance. The standard Tk interface remains fully functional.
    ctk = None
    HAS_CUSTOMTKINTER = False

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk
import pyperclip
import qrcode
import requests

API_BASE_URL = "http://127.0.0.1:8000"
T = TypeVar("T")


class URLShortenerApp:
    """Own the application window and dispatch all API work off the UI thread."""

    def __init__(self) -> None:
        self.root: Any = ctk.CTk() if HAS_CUSTOMTKINTER else tk.Tk()
        self.root.title("URL Shortener | College Project")
        self.root.geometry("1120x760")
        self.root.minsize(900, 620)

        self.url_var = tk.StringVar()
        self.alias_var = tk.StringVar()
        self.expiry_var = tk.StringVar(value="never")
        self.result_var = tk.StringVar(value="Your short link will appear here.")
        self.status_var = tk.StringVar(value="Starting local server on port 8000…")
        self.search_var = tk.StringVar()
        self.theme_var = tk.BooleanVar(value=True)
        self.current_short_url = ""
        self.links: list[dict[str, Any]] = []
        self.qr_image: Any = None

        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("blue")

        self._build_window()
        self.search_var.trace_add("write", lambda *_: self._render_history())
        self._check_server()

    def _frame(self, parent: Any, **kwargs: Any) -> Any:
        return ctk.CTkFrame(parent, **kwargs) if HAS_CUSTOMTKINTER else ttk.Frame(parent)

    def _label(self, parent: Any, **kwargs: Any) -> Any:
        return ctk.CTkLabel(parent, **kwargs) if HAS_CUSTOMTKINTER else ttk.Label(parent, **kwargs)

    def _button(self, parent: Any, **kwargs: Any) -> Any:
        return ctk.CTkButton(parent, **kwargs) if HAS_CUSTOMTKINTER else ttk.Button(parent, **kwargs)

    def _entry(self, parent: Any, **kwargs: Any) -> Any:
        if HAS_CUSTOMTKINTER:
            return ctk.CTkEntry(parent, **kwargs)
        kwargs.pop("placeholder_text", None)
        return ttk.Entry(parent, **kwargs)

    def _build_window(self) -> None:
        """Construct the form, result card, analytics table, and status bar."""
        container = self._frame(self.root)
        container.pack(fill="both", expand=True, padx=18, pady=16)
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(3, weight=1)

        header = self._frame(container)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        header.grid_columnconfigure(0, weight=1)
        self._label(
            header,
            text="URL Shortener",
            font=("Arial", 25, "bold"),
        ).grid(row=0, column=0, sticky="w")
        self._label(
            header,
            text="FastAPI + SQLite desktop demonstration",
            font=("Arial", 12),
        ).grid(row=1, column=0, sticky="w")
        if HAS_CUSTOMTKINTER:
            ctk.CTkSwitch(
                header,
                text="Dark mode",
                variable=self.theme_var,
                command=self._toggle_theme,
            ).grid(row=0, column=1, rowspan=2, padx=6)
        else:
            ttk.Checkbutton(
                header,
                text="Dark mode",
                variable=self.theme_var,
                command=self._toggle_theme,
            ).grid(row=0, column=1, rowspan=2, padx=6)

        form = self._frame(container)
        form.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        form.grid_columnconfigure(1, weight=1)
        self._label(form, text="Long URL").grid(row=0, column=0, padx=10, pady=8, sticky="w")
        self._entry(form, textvariable=self.url_var, placeholder_text="https://example.com" if HAS_CUSTOMTKINTER else "").grid(
            row=0, column=1, columnspan=3, padx=10, pady=8, sticky="ew"
        )
        self._label(form, text="Custom alias").grid(row=1, column=0, padx=10, pady=8, sticky="w")
        self._entry(form, textvariable=self.alias_var, placeholder_text="optional" if HAS_CUSTOMTKINTER else "").grid(
            row=1, column=1, padx=10, pady=8, sticky="ew"
        )
        self._label(form, text="Expiry").grid(row=1, column=2, padx=(10, 4), pady=8, sticky="e")
        if HAS_CUSTOMTKINTER:
            ctk.CTkOptionMenu(
                form,
                values=["never", "1 hour", "1 day", "7 days"],
                variable=self.expiry_var,
            ).grid(row=1, column=3, padx=10, pady=8, sticky="ew")
        else:
            ttk.Combobox(
                form,
                values=["never", "1 hour", "1 day", "7 days"],
                textvariable=self.expiry_var,
                state="readonly",
                width=12,
            ).grid(row=1, column=3, padx=10, pady=8, sticky="ew")
        self._button(form, text="Shorten URL", command=self.shorten_url).grid(
            row=2, column=0, columnspan=4, padx=10, pady=(4, 12), sticky="ew"
        )

        result = self._frame(container)
        result.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        result.grid_columnconfigure(0, weight=1)
        self._label(result, text="Result", font=("Arial", 15, "bold")).grid(
            row=0, column=0, padx=10, pady=(10, 2), sticky="w"
        )
        self._label(result, textvariable=self.result_var, wraplength=700).grid(
            row=1, column=0, padx=10, pady=8, sticky="w"
        )
        actions = self._frame(result)
        actions.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="w")
        self._button(actions, text="Copy", command=self.copy_link, width=100).grid(row=0, column=0, padx=(0, 8))
        self._button(actions, text="Open in browser", command=self.open_link, width=130).grid(row=0, column=1)
        self.qr_label = self._label(result, text="QR code appears here")
        self.qr_label.grid(row=0, column=1, rowspan=3, padx=20, pady=10)

        history = self._frame(container)
        history.grid(row=3, column=0, sticky="nsew")
        history.grid_columnconfigure(0, weight=1)
        history.grid_rowconfigure(1, weight=1)
        history_top = self._frame(history)
        history_top.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        history_top.grid_columnconfigure(1, weight=1)
        self._label(history_top, text="History", font=("Arial", 15, "bold")).grid(row=0, column=0, padx=(0, 12))
        self._entry(history_top, textvariable=self.search_var, placeholder_text="Search links…" if HAS_CUSTOMTKINTER else "").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        self._button(history_top, text="Refresh", command=self.refresh_history, width=90).grid(row=0, column=2, padx=4)
        self._button(history_top, text="Delete selected", command=self.delete_selected, width=125).grid(row=0, column=3)

        columns = ("id", "short_code", "original_url", "click_count", "created_at", "expires_at")
        self.history_tree = ttk.Treeview(history, columns=columns, show="headings", selectmode="browse")
        headings = ("ID", "Short code", "Original URL", "Clicks", "Created", "Expiry")
        widths = (55, 110, 390, 70, 180, 180)
        for column, heading, width in zip(columns, headings, widths):
            self.history_tree.heading(column, text=heading)
            self.history_tree.column(column, width=width, anchor="w")
        vertical_scroll = ttk.Scrollbar(history, orient="vertical", command=self.history_tree.yview)
        horizontal_scroll = ttk.Scrollbar(history, orient="horizontal", command=self.history_tree.xview)
        self.history_tree.configure(yscrollcommand=vertical_scroll.set, xscrollcommand=horizontal_scroll.set)
        self.history_tree.grid(row=1, column=0, sticky="nsew", padx=(10, 0), pady=(0, 4))
        vertical_scroll.grid(row=1, column=1, sticky="ns", padx=(0, 10), pady=(0, 4))
        horizontal_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        self._label(container, textvariable=self.status_var, anchor="w").grid(
            row=4, column=0, sticky="ew", pady=(10, 0)
        )

    def _on_main_thread(self, callback: Callable[[], None]) -> None:
        """Schedule a callback safely on the Tk event loop."""
        self.root.after(0, callback)

    def _run_async(self, work: Callable[[], T], success: Callable[[T], None]) -> None:
        """Run blocking HTTP work in a daemon thread and marshal results to Tk."""
        def runner() -> None:
            try:
                result = work()
            except (requests.RequestException, ValueError) as error:
                self._on_main_thread(
                    lambda message=str(error): self._set_error(message)
                )
            except Exception as error:  # pragma: no cover - defensive UI boundary
                self._on_main_thread(
                    lambda message=f"Unexpected error: {error}": self._set_error(message)
                )
            else:
                self._on_main_thread(lambda: success(result))

        threading.Thread(target=runner, daemon=True).start()

    def _request_json(self, method: str, path: str, **kwargs: Any) -> Any:
        """Make an API call and turn response errors into clear GUI messages."""
        response = requests.request(method, f"{API_BASE_URL}{path}", timeout=6, **kwargs)
        if not response.ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise ValueError(str(detail).strip() or f"Server error ({response.status_code}).")
        return response.json() if response.content else None

    def _check_server(self) -> None:
        """Poll the server once after launch without freezing the GUI."""
        def check() -> list[dict[str, Any]]:
            return self._request_json("GET", "/api/links")

        def ready(links: list[dict[str, Any]]) -> None:
            self.links = links
            self._render_history()
            self.status_var.set("Server running on port 8000")

        self._run_async(check, ready)

    def shorten_url(self) -> None:
        """Submit the create request using a worker thread."""
        url = self.url_var.get().strip()
        if not url:
            self._set_error("Enter a URL before shortening it.")
            return
        payload = {"url": url, "expiry": self.expiry_var.get()}
        if self.alias_var.get().strip():
            payload["alias"] = self.alias_var.get().strip()
        self.status_var.set("Creating short link…")

        def create() -> dict[str, str]:
            return self._request_json("POST", "/api/shorten", json=payload)

        def created(data: dict[str, str]) -> None:
            self.current_short_url = data["short_url"]
            self.result_var.set(data["short_url"])
            self.status_var.set("Short link created successfully.")
            self._show_qr_code(data["short_url"])
            self.refresh_history()

        self._run_async(create, created)

    def _show_qr_code(self, url: str) -> None:
        """Generate the QR image after the API has returned a short URL."""
        qr = qrcode.QRCode(box_size=4, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        image.thumbnail((150, 150))
        if HAS_CUSTOMTKINTER:
            self.qr_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        else:
            self.qr_image = ImageTk.PhotoImage(image)
        self.qr_label.configure(image=self.qr_image, text="")

    def copy_link(self) -> None:
        """Copy the current short URL, with a Tk clipboard fallback."""
        if not self.current_short_url:
            self._set_error("Create a short link first.")
            return
        try:
            pyperclip.copy(self.current_short_url)
        except pyperclip.PyperclipException:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.current_short_url)
        self.status_var.set("Short link copied to clipboard.")

    def open_link(self) -> None:
        """Open the current link in the system browser."""
        if not self.current_short_url:
            self._set_error("Create a short link first.")
            return
        webbrowser.open_new_tab(self.current_short_url)
        self.status_var.set("Opened short link in your browser.")

    def refresh_history(self) -> None:
        """Reload history from the API in a worker thread."""
        self.status_var.set("Refreshing history…")

        def loaded(links: list[dict[str, Any]]) -> None:
            self.links = links
            self._render_history()
            self.status_var.set(f"Loaded {len(links)} link(s). Server running on port 8000")

        self._run_async(lambda: self._request_json("GET", "/api/links"), loaded)

    def _render_history(self) -> None:
        """Render the locally filtered history records in the table."""
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        query = self.search_var.get().strip().lower()
        for link in self.links:
            searchable = f"{link['short_code']} {link['original_url']}".lower()
            if query and query not in searchable:
                continue
            self.history_tree.insert(
                "",
                "end",
                values=(
                    link["id"],
                    link["short_code"],
                    link["original_url"],
                    link["click_count"],
                    link["created_at"].replace("T", " ")[:19],
                    (link["expires_at"] or "Never").replace("T", " ")[:19],
                ),
            )

    def delete_selected(self) -> None:
        """Delete the selected table item after an explicit confirmation."""
        selection = self.history_tree.selection()
        if not selection:
            self._set_error("Select a link in history first.")
            return
        values = self.history_tree.item(selection[0], "values")
        short_code = values[1]
        if not messagebox.askyesno("Delete short link", f"Delete '{short_code}' permanently?"):
            return
        self.status_var.set("Deleting link…")

        def deleted(_: Any) -> None:
            self.status_var.set("Link deleted.")
            self.refresh_history()

        self._run_async(lambda: self._request_json("DELETE", f"/api/links/{short_code}"), deleted)

    def _toggle_theme(self) -> None:
        """Toggle CustomTkinter appearance, or a simple Tk background fallback."""
        if HAS_CUSTOMTKINTER:
            ctk.set_appearance_mode("dark" if self.theme_var.get() else "light")
        else:
            color = "#2b2b2b" if self.theme_var.get() else "#f0f0f0"
            self.root.configure(background=color)

    def _set_error(self, message: str) -> None:
        """Display concise failures in the always-visible status bar."""
        self.status_var.set(f"Error: {message}")

    def run(self) -> None:
        """Start the GUI event loop."""
        self.root.mainloop()

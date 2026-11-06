#!/usr/bin/env python3
"""Launch the local exporter inside a native desktop window."""
from __future__ import annotations

import threading
import tkinter
from tkinter import messagebox

import webview
from werkzeug.serving import make_server

from app import app


def main() -> None:
    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        webview.create_window(
            "SoundCloud Archive",
            f"http://127.0.0.1:{server.server_port}",
            min_size=(760, 620),
        )
        webview.start()
    finally:
        server.shutdown()
        server_thread.join(timeout=3)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror(
            "SoundCloud Archive could not start",
            f"{type(exc).__name__}: {exc}\n\n"
            "On Windows, install the Microsoft Edge WebView2 Runtime and try again.",
        )
        raise

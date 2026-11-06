#!/usr/bin/env python3
"""Launch the local exporter inside a native desktop window."""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path


def data_dir() -> Path:
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "SoundCloud Archive"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SoundCloud Archive"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "soundcloud-archive"


def smoke_test() -> None:
    from werkzeug.serving import make_server

    from app import app

    import webview

    if sys.platform == "win32":
        import webview.platforms.edgechromium
    elif sys.platform == "darwin":
        import webview.platforms.cocoa

    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        deadline = time.monotonic() + 30
        last_error = None
        while time.monotonic() < deadline:
            try:
                page_response = urllib.request.urlopen(url, timeout=10)
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = exc
                time.sleep(0.1)
                continue
            with page_response:
                page = page_response.read().decode("utf-8")
                if page_response.status != 200 or "CloudSnatch" not in page or "Following lists" not in page:
                    raise RuntimeError("The packaged desktop UI did not return its expected page.")
            for resource in ("/static/app.js", "/static/style.css"):
                with urllib.request.urlopen(url + resource, timeout=10) as response:
                    if response.status != 200 or not response.read():
                        raise RuntimeError(f"The packaged desktop UI resource is missing: {resource}")
            print("Desktop app smoke test passed.")
            return
        raise RuntimeError(f"The local desktop app did not become ready: {last_error}")
    finally:
        server.shutdown()
        server_thread.join(timeout=3)


def main() -> None:
    from werkzeug.serving import make_server

    from app import app

    if "--smoke-test" in sys.argv:
        smoke_test()
        return

    import webview

    server = make_server("127.0.0.1", 0, app, threaded=True)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    try:
        webview.create_window(
            "CloudSnatch",
            f"http://127.0.0.1:{server.server_port}",
            min_size=(760, 620),
        )
        webview.start(gui="edgechromium" if sys.platform == "win32" else None, debug=False)
    finally:
        server.shutdown()
        server_thread.join(timeout=3)


def show_startup_error(exc: Exception) -> None:
    log_path = data_dir() / "startup-error.log"
    details = f"{type(exc).__name__}: {exc}"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(traceback.format_exc() + "\n")
    except OSError:
        log_path = Path("startup-error.log")

    message = (
        f"{details}\n\n"
        f"Startup details were saved to:\n{log_path}\n\n"
        "On Windows, confirm that Microsoft Edge WebView2 Runtime is installed, "
        "then try launching CloudSnatch again."
    )
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror("CloudSnatch could not start", message, parent=root)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        show_startup_error(exc)
        raise

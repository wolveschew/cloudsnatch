#!/usr/bin/env python3
"""Local desktop UI for exporting public SoundCloud collections."""
from __future__ import annotations

import copy
import os
import sys
import threading
from pathlib import Path
from platform import system

from flask import Flask, jsonify, render_template, request, send_from_directory

from exporter import export_profile, load_json, normalize_profile_url

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
if system() == "Windows":
    DATA_HOME = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    OUTPUT = DATA_HOME / "SoundCloud Archive"
elif system() == "Darwin":
    OUTPUT = Path.home() / "Library" / "Application Support" / "SoundCloud Archive"
else:
    OUTPUT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "soundcloud-archive"

app = Flask(
    __name__,
    template_folder=str(ROOT / "templates"),
    static_folder=str(ROOT / "static"),
)
app.config["OUTPUT_DIR"] = str(OUTPUT)
_lock = threading.Lock()
_job = {
    "running": False,
    "profile_url": None,
    "status": "idle",
    "categories": {},
    "error": None,
    "report": None,
}


def output_dir() -> Path:
    return Path(app.config["OUTPUT_DIR"])


def update_progress(category: str, count: int, message: str) -> None:
    with _lock:
        _job.setdefault("categories", {})[category] = {
            "status": "fetching",
            "count": count,
            "message": message,
        }
        _job["status"] = f"Fetching public {category}: {message} ({count})"


def run_job(profile_url: str, force: bool) -> None:
    try:
        report = export_profile(profile_url, output_dir(), update_progress, force)
        with _lock:
            _job["report"] = report
            _job["categories"] = report.get("categories", {})
            _job["status"] = "Export finished. Review each category status below."
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        with _lock:
            _job["error"] = error
            _job["status"] = "Export stopped. Review the error and resume when ready."
    finally:
        with _lock:
            _job["running"] = False


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/export")
def start_export():
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Send a JSON object with a profile URL."}), 400
    retry = body.get("retry", False)
    if not isinstance(retry, bool):
        return jsonify({"error": "The retry setting must be true or false."}), 400
    try:
        profile_url = normalize_profile_url(str(body.get("url", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with _lock:
        if _job["running"]:
            return jsonify({"error": "An export is already running."}), 409
        _job.update({
            "running": True,
            "profile_url": profile_url,
            "status": "Starting export…",
            "categories": {},
            "error": None,
            "report": None,
        })
        thread = threading.Thread(target=run_job, args=(profile_url, retry), daemon=True)
        try:
            thread.start()
        except RuntimeError as exc:
            _job.update({"running": False, "error": str(exc), "status": "Could not start the export."})
            return jsonify({"error": "Could not start the export thread."}), 500
    return jsonify({"ok": True})


@app.get("/api/status")
def status():
    with _lock:
        snapshot = copy.deepcopy(_job)
    if not snapshot["running"] and snapshot["report"] is None:
        report = load_json(output_dir() / "report.json", None)
        if isinstance(report, dict) and (
            snapshot["profile_url"] is None
            or report.get("profile_url") == snapshot["profile_url"]
        ):
            snapshot["report"] = report
            snapshot["categories"] = report.get("categories", {})
    return jsonify(snapshot)


@app.get("/api/files/<name>")
def download(name: str):
    allowed = {"likes.json", "playlists.json", "report.json", "state.json"}
    if name not in allowed:
        return jsonify({"error": "Not found"}), 404
    if not (output_dir() / name).is_file():
        return jsonify({"error": "File not available yet"}), 404
    return send_from_directory(output_dir(), name, as_attachment=True)


if __name__ == "__main__":
    # Bind loopback only; the desktop wrapper uses an ephemeral local port.
    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)

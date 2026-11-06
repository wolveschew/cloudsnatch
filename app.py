#!/usr/bin/env python3
"""Local-only dark web UI for public SoundCloud export."""
from __future__ import annotations

import threading
from pathlib import Path
from flask import Flask, jsonify, render_template, request, send_from_directory

from exporter import export_profile, normalize_profile_url

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "soundcloud-export"
app = Flask(__name__)
_lock = threading.Lock()
_job = {"running": False, "profile_url": None, "status": "idle", "counts": {}, "error": None}


def update_progress(category: str, count: int, message: str) -> None:
    _job.setdefault("counts", {})[category] = count
    _job["status"] = f"{category}: {message} ({count})"


def run_job(profile_url: str, force: bool) -> None:
    try:
        report = export_profile(profile_url, OUTPUT, update_progress, force)
        _job["report"] = report
        _job["status"] = "Export finished. Review each category status below."
    except Exception as exc:
        _job["error"] = f"{type(exc).__name__}: {exc}"
        _job["status"] = "Export stopped with an error. Check the report and resume by starting again."
    finally:
        _job["running"] = False


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/export")
def start_export():
    body = request.get_json(silent=True) or {}
    try:
        profile_url = normalize_profile_url(str(body.get("url", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    with _lock:
        if _job["running"]:
            return jsonify({"error": "An export is already running."}), 409
        _job.update({"running": True, "profile_url": profile_url, "status": "Starting…", "counts": {}, "error": None, "report": None})
        thread = threading.Thread(target=run_job, args=(profile_url, bool(body.get("retry"))), daemon=True)
        thread.start()
    return jsonify({"ok": True})


@app.get("/api/status")
def status():
    return jsonify(_job)


@app.get("/api/files/<name>")
def download(name: str):
    allowed = {"likes.json", "playlists.json", "report.json", "state.json"}
    if name not in allowed:
        return jsonify({"error": "Not found"}), 404
    if not (OUTPUT / name).is_file():
        return jsonify({"error": "File not available yet"}), 404
    return send_from_directory(OUTPUT, name, as_attachment=True)


if __name__ == "__main__":
    # Bind loopback only; do not expose this unauthenticated local tool to a network.
    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)

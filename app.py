#!/usr/bin/env python3
"""Local desktop UI for exporting public SoundCloud collections."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from platform import system
from typing import Any
from urllib.parse import unquote, urlparse

from flask import Flask, jsonify, render_template, request, send_from_directory

from exporter import atomic_json, csv_preview, export_profile, load_json, normalize_profile_url

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
    "latest_item": None,
}
_DEFAULT_SETTINGS = {"accent": "orange", "compact": False}
_ACCENT_CHOICES = {"orange", "amber", "blue"}


def output_dir() -> Path:
    return Path(app.config["OUTPUT_DIR"])


def account_output_dir(profile_url: str) -> Path:
    normalized = normalize_profile_url(profile_url)
    username = unquote(urlparse(normalized).path.strip("/"))
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", username).strip(".-_") or "soundcloud-account"
    suffix = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    return output_dir() / "accounts" / f"{slug}-{suffix}"


def migrate_legacy_account(profile_url: str) -> Path:
    target = account_output_dir(profile_url)
    legacy = output_dir()
    files = ("likes.json", "playlists.json", "report.json", "state.json")
    matching = []
    for name in files:
        source = legacy / name
        saved = load_json(source, None)
        if isinstance(saved, dict) and saved.get("profile_url") == profile_url:
            matching.append(source)
    if matching:
        target.mkdir(parents=True, exist_ok=True)
        for source in matching:
            destination = target / source.name
            if not destination.exists():
                shutil.copy2(source, destination)
    return target


def open_folder(path: Path) -> None:
    if system() == "Windows":
        opener = getattr(os, "startfile", None)
        if opener is None:
            raise OSError("Windows Explorer could not be started.")
        opener(str(path))
    elif system() == "Darwin":
        subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def update_progress(
    category: str,
    count: int,
    message: str,
    entry: dict[str, Any] | None = None,
) -> None:
    with _lock:
        _job.setdefault("categories", {})[category] = {
            "status": "fetching",
            "count": count,
            "message": message,
        }
        _job["status"] = f"Fetching public {category}: {message} ({count})"
        if entry is not None:
            json_preview = json.dumps(entry, ensure_ascii=False, indent=2)
            _job["latest_item"] = {
                "category": category,
                "count": count,
                "title": str(entry.get("title") or entry.get("name") or "Untitled item"),
                "json": json_preview[:6000],
                "json_truncated": len(json_preview) > 6000,
                "csv": csv_preview(entry),
                "checkpoint": message == "checkpoint saved",
            }


def run_job(profile_url: str, force: bool) -> None:
    try:
        report = export_profile(profile_url, migrate_legacy_account(profile_url), update_progress, force)
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
            "latest_item": None,
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
    target_dir = account_output_dir(snapshot["profile_url"]) if snapshot["profile_url"] else output_dir()
    snapshot["account_directory"] = str(target_dir)
    if not snapshot["running"] and snapshot["report"] is None:
        report = load_json(target_dir / "report.json", None)
        if isinstance(report, dict) and (
            snapshot["profile_url"] is None
            or report.get("profile_url") == snapshot["profile_url"]
        ):
            snapshot["report"] = report
            snapshot["categories"] = report.get("categories", {})
    return jsonify(snapshot)


@app.post("/api/open-folder")
def open_account_folder():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Send the account profile URL as a JSON object."}), 400
    try:
        profile_url = normalize_profile_url(str(body.get("url", "")))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    folder = migrate_legacy_account(profile_url)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        open_folder(folder)
    except OSError as exc:
        return jsonify({"error": f"Could not open the account folder: {exc}"}), 500
    return jsonify({"ok": True, "path": str(folder)})


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    settings_path = output_dir() / "settings.json"
    if request.method == "GET":
        saved = load_json(settings_path, {})
        if not isinstance(saved, dict):
            saved = {}
        accent = saved.get("accent")
        return jsonify({
            "accent": accent if isinstance(accent, str) and accent in _ACCENT_CHOICES else _DEFAULT_SETTINGS["accent"],
            "compact": saved.get("compact") if isinstance(saved.get("compact"), bool) else _DEFAULT_SETTINGS["compact"],
        })

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Send appearance settings as a JSON object."}), 400
    accent = body.get("accent")
    compact = body.get("compact")
    if not isinstance(accent, str) or accent not in _ACCENT_CHOICES or not isinstance(compact, bool):
        return jsonify({"error": "Choose a supported accent and a true/false compact setting."}), 400
    saved = {"accent": accent, "compact": compact}
    atomic_json(settings_path, saved)
    return jsonify(saved)


@app.get("/api/files/<name>")
def download(name: str):
    allowed = {"likes.json", "playlists.json", "likes.csv", "playlists.csv", "report.json", "state.json"}
    if name not in allowed:
        return jsonify({"error": "Not found"}), 404
    with _lock:
        profile_url = _job["profile_url"]
    directory = account_output_dir(profile_url) if profile_url else output_dir()
    if not (directory / name).is_file():
        return jsonify({"error": "File not available yet"}), 404
    return send_from_directory(directory, name, as_attachment=True)


if __name__ == "__main__":
    # Bind loopback only; the desktop wrapper uses an ephemeral local port.
    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)

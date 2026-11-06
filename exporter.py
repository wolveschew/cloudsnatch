#!/usr/bin/env python3
"""Export public SoundCloud likes and playlists with resumable local checkpoints."""
from __future__ import annotations

import csv
import io
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from yt_dlp import YoutubeDL

UNSUPPORTED = {
    "followings": "Not available through the supported public yt-dlp SoundCloud extractor. No private or undocumented endpoint is used.",
}
CATEGORIES = {"likes": "likes", "playlists": "sets"}
CSV_FIELDS = (
    "id",
    "title",
    "url",
    "webpage_url",
    "uploader",
    "uploader_id",
    "duration",
    "timestamp",
    "upload_date",
    "track_count",
    "description",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def normalize_profile_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {
        "soundcloud.com", "www.soundcloud.com", "m.soundcloud.com"
    }:
        raise ValueError("Please enter a SoundCloud profile URL.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 1 or parsed.query or parsed.fragment:
        raise ValueError("Please enter a profile URL only, such as https://soundcloud.com/artist.")
    return f"https://soundcloud.com/{parts[0]}"


def stable_id(entry: dict[str, Any]) -> str:
    return str(entry.get("id") or entry.get("url") or entry.get("webpage_url") or json.dumps(entry, sort_keys=True))


def csv_values(entry: dict[str, Any]) -> dict[str, Any]:
    values = {field: entry.get(field, "") for field in CSV_FIELDS}
    values["url"] = entry.get("url") or entry.get("webpage_url") or ""
    values["webpage_url"] = entry.get("webpage_url") or entry.get("url") or ""
    values["uploader"] = entry.get("uploader") or entry.get("artist") or ""
    values["uploader_id"] = entry.get("uploader_id") or entry.get("artist_id") or ""
    values["track_count"] = entry.get("track_count") or entry.get("playlist_count") or ""
    description = values["description"]
    values["description"] = description if isinstance(description, str) else ""
    return values


def csv_line(entry: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator="")
    writer.writerow(csv_values(entry))
    return stream.getvalue()


def csv_preview(entry: dict[str, Any]) -> str:
    return ",".join(CSV_FIELDS) + "\n" + csv_line(entry)


def write_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(csv_values(entry) for entry in entries)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def export_category(
    profile_url: str,
    category: str,
    output_dir: Path,
    progress: Callable[..., None],
    force: bool = False,
) -> dict[str, Any]:
    """Exhaust yt-dlp's paginated collection iterator; checkpoint every 25 items.

    On resume, refetch the public collection from its beginning and de-duplicate by
    stable item ID against the partial checkpoint. This is safe, though not a seek.
    """
    if category not in CATEGORIES:
        raise ValueError(f"Unsupported category: {category}")

    output_dir.mkdir(parents=True, exist_ok=True)
    data_path = output_dir / f"{category}.json"
    state_path = output_dir / "state.json"
    loaded_state = load_json(state_path, {})
    state = loaded_state if isinstance(loaded_state, dict) else {}
    if state.get("profile_url") != profile_url:
        state = {"profile_url": profile_url, "categories": {}}
    if not isinstance(state.get("categories"), dict):
        state["categories"] = {}

    if data_path.exists() and not force:
        cached = load_json(data_path, {})
        if isinstance(cached, dict) and cached.get("profile_url") == profile_url and cached.get("complete"):
            cached_entries = cached.get("entries", [])
            if isinstance(cached_entries, list):
                write_csv(
                    output_dir / f"{category}.csv",
                    [entry for entry in cached_entries if isinstance(entry, dict)],
                )
            progress(category, cached.get("count", 0), "already complete")
            return cached

    partial = load_json(data_path, {}) if not force else {}
    if not isinstance(partial, dict):
        partial = {}
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    if partial.get("profile_url") == profile_url:
        partial_entries = partial.get("entries", [])
        if not isinstance(partial_entries, list):
            partial_entries = []
        for entry in partial_entries:
            if isinstance(entry, dict):
                key = stable_id(entry)
                if key not in seen:
                    seen.add(key)
                    entries.append(entry)

    source_url = f"{profile_url}/{CATEGORIES[category]}"
    csv_path = output_dir / f"{category}.csv"
    state.setdefault("categories", {})[category] = {
        "status": "running", "count": len(entries), "updated_at": utc_now()
    }
    atomic_json(state_path, state)
    progress(
        category,
        len(entries),
        "resuming saved checkpoint" if entries else "connecting to public collection",
    )

    ydl_options = {
        "quiet": True,
        "no_warnings": False,
        "ignoreerrors": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "playlistend": None,
        "retries": 5,
        "extractor_retries": 3,
        "socket_timeout": 30,
        "noplaylist": False,
    }

    def checkpoint(complete: bool, title: str | None = None, collection_id: Any = None) -> None:
        payload = {
            "profile_url": profile_url,
            "collection_url": source_url,
            "category": category,
            "collection_id": collection_id,
            "title": title,
            "count": len(entries),
            "complete": complete,
            "exported_at": utc_now(),
            "csv_file": csv_path.name,
            "entries": entries,
        }
        atomic_json(data_path, payload)
        state["categories"][category] = {
            "status": "complete" if complete else "incomplete",
            "count": len(entries), "updated_at": utc_now(),
            "file": data_path.name,
        }
        atomic_json(state_path, state)

    title = None
    collection_id = None
    try:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as csv_stream:
            csv_writer = csv.DictWriter(csv_stream, fieldnames=CSV_FIELDS)
            csv_writer.writeheader()
            csv_writer.writerows(csv_values(entry) for entry in entries)
            csv_stream.flush()

            with YoutubeDL(ydl_options) as ydl:
                info = ydl.extract_info(source_url, download=False)
                if not isinstance(info, dict) or info.get("entries") is None:
                    raise RuntimeError("SoundCloud returned no public collection. It may be private, blocked, or unavailable.")
                title = info.get("title")
                collection_id = info.get("id")
                iterator = iter(info["entries"])
                new_since_checkpoint = 0
                for entry in iterator:
                    if not isinstance(entry, dict):
                        continue
                    key = stable_id(entry)
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append(entry)
                    csv_writer.writerow(csv_values(entry))
                    csv_stream.flush()
                    new_since_checkpoint += 1
                    if new_since_checkpoint >= 25:
                        checkpoint(False, title, collection_id)
                        new_since_checkpoint = 0
                        progress(category, len(entries), "checkpoint saved", entry)
                    else:
                        progress(category, len(entries), "pending next checkpoint", entry)
                checkpoint(True, title, collection_id)
                if entries:
                    progress(category, len(entries), "checkpoint saved", entries[-1])
    except Exception:
        checkpoint(False, title, collection_id)
        raise
    return load_json(data_path, {})


def load_json(path: Path, fallback: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, json.JSONDecodeError):
        return fallback


def export_profile(
    profile: str,
    output_dir: Path,
    progress: Callable[..., None],
    force: bool = False,
) -> dict[str, Any]:
    profile_url = normalize_profile_url(profile)
    report_path = output_dir / "report.json"
    loaded_report = load_json(report_path, {})
    report = loaded_report if isinstance(loaded_report, dict) else {}
    if report.get("profile_url") != profile_url:
        report = {"profile_url": profile_url, "categories": {}}
    if not isinstance(report.get("categories"), dict):
        report["categories"] = {}

    errors: list[dict[str, str]] = []
    for category in CATEGORIES:
        try:
            result = export_category(profile_url, category, output_dir, progress, force)
            report["categories"][category] = {
                "status": "complete" if result.get("complete") else "incomplete",
                "count": result.get("count", 0),
                "file": f"{category}.json",
                "csv_file": f"{category}.csv",
            }
        except Exception as exc:
            errors.append({"category": category, "error": f"{type(exc).__name__}: {exc}"})
            checkpoint = load_json(output_dir / f"{category}.json", {})
            saved_checkpoint = (
                checkpoint
                if isinstance(checkpoint, dict) and checkpoint.get("profile_url") == profile_url
                else {}
            )
            failed_category = {"status": "failed", "error": errors[-1]["error"]}
            if saved_checkpoint:
                failed_category.update({
                    "count": saved_checkpoint.get("count", 0),
                    "file": f"{category}.json",
                    "csv_file": f"{category}.csv",
                })
            report["categories"][category] = failed_category
        atomic_json(report_path, report)

    report["categories"]["followings"] = {
        "status": "unsupported", "reason": UNSUPPORTED["followings"]
    }
    report["errors"] = errors
    report["exported_at"] = utc_now()
    report["note"] = "Public metadata export only. No account login, follow/like automation, or audio download is performed."
    atomic_json(report_path, report)
    return report

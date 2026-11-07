#!/usr/bin/env python3
"""Export public SoundCloud likes and playlists with resumable local checkpoints."""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import tempfile
import time
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
TRACK_CSV_FIELDS = (
    "playlist_id",
    "playlist_title",
    "track_id",
    "title",
    "url",
    "uploader",
    "duration",
    "timestamp",
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


def expected_count(info: dict[str, Any]) -> int | None:
    for key in ("playlist_count", "n_entries"):
        value = info.get(key)
        if isinstance(value, int) and value >= 0:
            return value
    return None


def is_transient_network_error(error: Exception) -> bool:
    messages = []
    current: BaseException | None = error
    while current is not None:
        messages.append(str(current).lower())
        current = current.__cause__ or current.__context__
    message = " ".join(messages)
    return any(
        marker in message
        for marker in (
            "timed out",
            "timeout",
            "temporarily unavailable",
            "temporary failure",
            "connection reset",
            "connection aborted",
            "remote end closed",
            "http error 408",
            "http error 429",
            "http error 500",
            "http error 502",
            "http error 503",
            "http error 504",
        )
    )


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

    partial = load_json(data_path, {}) if not force else {}
    if not isinstance(partial, dict):
        partial = {}
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    if partial.get("profile_url") == profile_url and not partial.get("complete"):
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
        None,
        None,
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
        "socket_timeout": 60,
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
            "total": total,
            "complete": complete,
            "exported_at": utc_now(),
            "csv_file": csv_path.name,
            "entries": entries,
        }
        atomic_json(data_path, payload)
        state["categories"][category] = {
            "status": "complete" if complete else "incomplete",
            "count": len(entries), "total": total, "updated_at": utc_now(),
            "file": data_path.name,
        }
        atomic_json(state_path, state)

    title = None
    collection_id = None
    total = None
    max_collection_attempts = 3
    for attempt in range(1, max_collection_attempts + 1):
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
                    total = expected_count(info)
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
                            progress(category, len(entries), "checkpoint saved", entry, total)
                        else:
                            progress(category, len(entries), "pending next checkpoint", entry, total)
                    checkpoint(True, title, collection_id)
                    if entries:
                        progress(category, len(entries), "checkpoint saved", entries[-1], total)
            break
        except Exception as error:
            checkpoint(False, title, collection_id)
            if attempt == max_collection_attempts or not is_transient_network_error(error):
                raise
            progress(
                category,
                len(entries),
                f"temporary network error; retrying ({attempt + 1}/{max_collection_attempts})",
                None,
                None,
            )
            time.sleep(attempt)
    return load_json(data_path, {})


def export_playlist_tracks(
    profile_url: str,
    output_dir: Path,
    progress: Callable[..., None],
    force: bool = False,
) -> dict[str, Any]:
    """Snapshot public tracks inside each playlist using yt-dlp's SoundCloud extractor."""
    playlist_data = load_json(output_dir / "playlists.json", {})
    if (
        not isinstance(playlist_data, dict)
        or playlist_data.get("profile_url") != profile_url
        or not playlist_data.get("complete")
    ):
        raise RuntimeError("Export the public playlist list before expanding its tracks.")
    playlists = playlist_data.get("entries", [])
    if not isinstance(playlists, list):
        raise RuntimeError("The saved playlist snapshot has an invalid entries list.")

    data_path = output_dir / "playlist_tracks.json"
    csv_path = output_dir / "playlist_tracks.csv"
    state_path = output_dir / "state.json"
    state = load_json(state_path, {})
    if not isinstance(state, dict) or state.get("profile_url") != profile_url:
        state = {"profile_url": profile_url, "categories": {}}
    if not isinstance(state.get("categories"), dict):
        state["categories"] = {}

    partial = load_json(data_path, {}) if not force else {}
    entries = []
    seen: set[tuple[str, str]] = set()
    if (
        isinstance(partial, dict)
        and partial.get("profile_url") == profile_url
        and not partial.get("complete")
    ):
        old_entries = partial.get("entries", [])
        if isinstance(old_entries, list):
            for entry in old_entries:
                if isinstance(entry, dict):
                    key = (str(entry.get("playlist_id", "")), str(entry.get("track_id") or entry.get("id") or ""))
                    if key not in seen:
                        seen.add(key)
                        entries.append(entry)

    total = sum(
        int(item["track_count"])
        for item in playlists
        if isinstance(item, dict)
        and isinstance(item.get("track_count"), int)
        and item["track_count"] >= 0
    ) if playlists else 0
    if total == 0 and playlists:
        total = None
    state.setdefault("categories", {})["playlist_tracks"] = {
        "status": "running",
        "count": len(entries),
        "total": total,
        "updated_at": utc_now(),
    }
    atomic_json(state_path, state)
    progress(
        "playlist_tracks",
        len(entries),
        "resuming saved checkpoint" if entries else "opening public playlists",
        None,
        total,
    )

    ydl_options = {
        "quiet": True,
        "no_warnings": False,
        "ignoreerrors": False,
        "extract_flat": "in_playlist",
        "skip_download": True,
        "retries": 5,
        "extractor_retries": 3,
        "socket_timeout": 60,
        "noplaylist": False,
    }

    def checkpoint(complete: bool) -> None:
        payload = {
            "profile_url": profile_url,
            "category": "playlist_tracks",
            "count": len(entries),
            "total": total,
            "complete": complete,
            "exported_at": utc_now(),
            "csv_file": csv_path.name,
            "entries": entries,
        }
        atomic_json(data_path, payload)
        state["categories"]["playlist_tracks"] = {
            "status": "complete" if complete else "incomplete",
            "count": len(entries),
            "total": total,
            "updated_at": utc_now(),
            "file": data_path.name,
            "csv_file": csv_path.name,
        }
        atomic_json(state_path, state)

    try:
        with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TRACK_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(track_csv_values(entry) for entry in entries)
            stream.flush()
            with YoutubeDL(ydl_options) as ydl:
                new_since_checkpoint = 0
                for playlist in playlists:
                    if not isinstance(playlist, dict):
                        continue
                    playlist_url = playlist.get("webpage_url") or playlist.get("url")
                    parsed_url = urlparse(playlist_url) if isinstance(playlist_url, str) else None
                    if (
                        parsed_url is None
                        or parsed_url.scheme != "https"
                        or parsed_url.hostname not in {
                            "soundcloud.com",
                            "www.soundcloud.com",
                            "m.soundcloud.com",
                        }
                    ):
                        raise RuntimeError(
                            f"Could not identify a public SoundCloud URL for playlist "
                            f"{playlist.get('title') or playlist.get('id') or 'without a name'}."
                        )
                    playlist_info = ydl.extract_info(playlist_url, download=False)
                    if not isinstance(playlist_info, dict) or playlist_info.get("entries") is None:
                        raise RuntimeError(
                            f"Could not read public tracks for playlist "
                            f"{playlist.get('title') or playlist.get('id') or playlist_url}."
                        )
                    playlist_id = str(playlist.get("id") or stable_id(playlist))
                    playlist_title = str(playlist.get("title") or "Untitled playlist")
                    for track in playlist_info["entries"]:
                        if not isinstance(track, dict):
                            continue
                        track_id = str(track.get("id") or "")
                        key = (playlist_id, track_id or stable_id(track))
                        if key in seen:
                            continue
                        row = {
                            "playlist_id": playlist_id,
                            "playlist_title": playlist_title,
                            "track_id": track_id,
                            "id": track_id,
                            "title": str(track.get("title") or "Untitled track"),
                            "url": track.get("webpage_url") or track.get("url") or "",
                            "webpage_url": track.get("webpage_url") or track.get("url") or "",
                            "uploader": track.get("uploader") or track.get("artist") or "",
                            "duration": track.get("duration") or "",
                            "timestamp": track.get("timestamp") or "",
                        }
                        seen.add(key)
                        entries.append(row)
                        writer.writerow(track_csv_values(row))
                        stream.flush()
                        new_since_checkpoint += 1
                        progress("playlist_tracks", len(entries), "track saved", row, total)
                        if new_since_checkpoint >= 25:
                            checkpoint(False)
                            new_since_checkpoint = 0
                            progress("playlist_tracks", len(entries), "checkpoint saved", row, total)
            checkpoint(True)
    except Exception:
        checkpoint(False)
        raise
    result = load_json(data_path, {})
    if entries:
        progress("playlist_tracks", len(entries), "checkpoint saved", entries[-1], total)
    return result


def track_csv_values(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "playlist_id": entry.get("playlist_id", ""),
        "playlist_title": entry.get("playlist_title", ""),
        "track_id": entry.get("track_id") or entry.get("id") or "",
        "title": entry.get("title", ""),
        "url": entry.get("url") or entry.get("webpage_url") or "",
        "uploader": entry.get("uploader", ""),
        "duration": entry.get("duration", ""),
        "timestamp": entry.get("timestamp", ""),
    }


def track_csv_preview(entry: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=TRACK_CSV_FIELDS, lineterminator="")
    writer.writerow(track_csv_values(entry))
    return ",".join(TRACK_CSV_FIELDS) + "\n" + stream.getvalue()


def write_track_csv(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=TRACK_CSV_FIELDS)
            writer.writeheader()
            writer.writerows(track_csv_values(entry) for entry in entries)
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def create_snapshot(output_dir: Path, report: dict[str, Any]) -> str | None:
    category_files = {
        "likes": ("likes.json", "likes.csv"),
        "playlists": ("playlists.json", "playlists.csv"),
        "playlist_tracks": ("playlist_tracks.json", "playlist_tracks.csv"),
    }
    categories = report.get("categories", {})
    source_files = ["report.json"]
    if isinstance(categories, dict):
        for category, filenames in category_files.items():
            status = categories.get(category)
            if isinstance(status, dict) and status.get("status") == "complete":
                source_files.extend(filenames)
    existing = [output_dir / name for name in source_files if (output_dir / name).is_file()]
    if not existing:
        return None

    snapshot_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report["snapshot_id"] = snapshot_id
    atomic_json(output_dir / "report.json", report)
    snapshots_dir = output_dir / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=snapshots_dir))
    destination = snapshots_dir / snapshot_id
    try:
        for source in existing:
            shutil.copy2(source, temporary / source.name)
        atomic_json(temporary / "manifest.json", {
            "snapshot_id": snapshot_id,
            "profile_url": report.get("profile_url"),
            "exported_at": report.get("exported_at"),
            "categories": report.get("categories", {}),
        })
        os.replace(temporary, destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return snapshot_id


def list_snapshots(output_dir: Path) -> list[dict[str, Any]]:
    snapshots_dir = output_dir / "snapshots"
    if not snapshots_dir.is_dir():
        return []
    snapshots = []
    for path in sorted(snapshots_dir.iterdir(), reverse=True):
        manifest = load_json(path / "manifest.json", {})
        if isinstance(manifest, dict) and manifest.get("snapshot_id") == path.name:
            snapshots.append(manifest)
    return snapshots


def delete_snapshot_history(output_dir: Path) -> None:
    snapshots_dir = output_dir / "snapshots"
    if snapshots_dir.is_symlink():
        snapshots_dir.unlink()
    elif snapshots_dir.is_dir():
        shutil.rmtree(snapshots_dir)


def compare_latest_snapshots(output_dir: Path) -> dict[str, Any]:
    snapshots = list_snapshots(output_dir)
    if len(snapshots) < 2:
        raise ValueError("Create at least two snapshots before comparing them.")
    older, newer = snapshots[1], snapshots[0]
    older_dir = output_dir / "snapshots" / str(older["snapshot_id"])
    newer_dir = output_dir / "snapshots" / str(newer["snapshot_id"])

    def item_ids(snapshot_dir: Path, category: str) -> set[str]:
        data = load_json(snapshot_dir / f"{category}.json", {})
        records = data.get("entries", []) if isinstance(data, dict) else []
        if not isinstance(records, list):
            return set()
        ids = set()
        for record in records:
            if not isinstance(record, dict):
                continue
            item_id = record.get("track_id") or record.get("id")
            if item_id is None:
                continue
            if category == "playlist_tracks":
                item_id = f"{record.get('playlist_id', '')}:{item_id}"
            ids.add(str(item_id))
        return ids

    changes = {}
    older_categories = older.get("categories")
    newer_categories = newer.get("categories")
    for category in ("likes", "playlists", "playlist_tracks"):
        older_status = older_categories.get(category, {}) if isinstance(older_categories, dict) else {}
        newer_status = newer_categories.get(category, {}) if isinstance(newer_categories, dict) else {}
        if (
            not isinstance(older_status, dict)
            or older_status.get("status") != "complete"
            or not isinstance(newer_status, dict)
            or newer_status.get("status") != "complete"
        ):
            changes[category] = {
                "available": False,
                "reason": "Not compared because one or both snapshots are incomplete for this category.",
            }
            continue
        previous = item_ids(older_dir, category)
        current = item_ids(newer_dir, category)
        added = sorted(current - previous)
        removed = sorted(previous - current)
        changes[category] = {
            "available": True,
            "added_count": len(added),
            "removed_count": len(removed),
            "added_ids": added[:500],
            "removed_ids": removed[:500],
            "truncated": len(added) > 500 or len(removed) > 500,
        }
    return {
        "older_snapshot": older,
        "newer_snapshot": newer,
        "categories": changes,
    }


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
                "total": result.get("total"),
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
                    "total": saved_checkpoint.get("total"),
                    "file": f"{category}.json",
                    "csv_file": f"{category}.csv",
                })
            report["categories"][category] = failed_category
        atomic_json(report_path, report)

    playlist_status = report["categories"].get("playlists", {})
    if not isinstance(playlist_status, dict) or playlist_status.get("status") != "complete":
        message = "Playlist tracks were not expanded because the public playlist list did not complete."
        errors.append({"category": "playlist_tracks", "error": message})
        report["categories"]["playlist_tracks"] = {"status": "failed", "error": message}
    else:
        try:
            result = export_playlist_tracks(profile_url, output_dir, progress, force)
            report["categories"]["playlist_tracks"] = {
                "status": "complete" if result.get("complete") else "incomplete",
                "count": result.get("count", 0),
                "total": result.get("total"),
                "file": "playlist_tracks.json",
                "csv_file": "playlist_tracks.csv",
            }
        except Exception as exc:
            errors.append({"category": "playlist_tracks", "error": f"{type(exc).__name__}: {exc}"})
            checkpoint = load_json(output_dir / "playlist_tracks.json", {})
            saved_checkpoint = (
                checkpoint
                if isinstance(checkpoint, dict) and checkpoint.get("profile_url") == profile_url
                else {}
            )
            failed_category = {"status": "failed", "error": errors[-1]["error"]}
            if saved_checkpoint:
                failed_category.update({
                    "count": saved_checkpoint.get("count", 0),
                    "total": saved_checkpoint.get("total"),
                    "file": "playlist_tracks.json",
                    "csv_file": "playlist_tracks.csv",
                })
            report["categories"]["playlist_tracks"] = failed_category

    report["categories"]["followings"] = {
        "status": "unsupported", "reason": UNSUPPORTED["followings"]
    }
    report["errors"] = errors
    report["exported_at"] = utc_now()
    report["note"] = "Public metadata export only. No account login, follow/like automation, or audio download is performed."
    report["snapshot_id"] = None
    atomic_json(report_path, report)
    report["snapshot_id"] = create_snapshot(output_dir, report)
    return report

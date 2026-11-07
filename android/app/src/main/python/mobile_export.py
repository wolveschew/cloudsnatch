"""Progress adapter for the Android app; all extraction stays in exporter.py."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from exporter import (
    atomic_json,
    compare_latest_snapshots,
    csv_preview,
    delete_snapshot_history,
    export_profile,
    list_snapshots,
    load_json,
    track_csv_preview,
)


def run_export(profile_url: str, output_dir: str, force: bool = False) -> str:
    directory = Path(output_dir)
    progress_path = directory / "mobile-progress.json"
    ids_path = directory / "mobile-track-ids.jsonl"
    last_write = 0.0
    written_ids: set[tuple[str, str]] = set()

    def append_track_id(category: str, entry: dict[str, Any]) -> None:
        if category not in {"likes", "playlist_tracks"}:
            return
        track_id = entry.get("track_id") or entry.get("id")
        if track_id is None:
            return
        key = (category, str(track_id))
        if key in written_ids:
            return
        with ids_path.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps({"category": category, "id": str(track_id)}, ensure_ascii=True) + "\n"
            )
            stream.flush()
        written_ids.add(key)

    directory.mkdir(parents=True, exist_ok=True)
    if progress_path.exists():
        progress_path.unlink()
    ids_path.write_text("", encoding="utf-8")
    if not force:
        for category, filename in (("likes", "likes.json"), ("playlist_tracks", "playlist_tracks.json")):
            saved = load_json(directory / filename, {})
            saved_entries = saved.get("entries", []) if isinstance(saved, dict) else []
            if isinstance(saved_entries, list) and isinstance(saved, dict) and not saved.get("complete"):
                for entry in saved_entries:
                    if isinstance(entry, dict):
                        append_track_id(category, entry)

    def update(
        category: str,
        count: int,
        message: str,
        entry: dict[str, Any] | None = None,
        total: int | None = None,
    ) -> None:
        nonlocal last_write
        if entry is not None:
            append_track_id(category, entry)
        now = time.monotonic()
        if entry is not None and count % 5 != 0 and now - last_write < 1:
            return
        latest = None
        if entry is not None:
            rendered = json.dumps(entry, ensure_ascii=False, indent=2)
            latest = {
                "category": category,
                "count": count,
                "id": str(entry.get("track_id") or entry.get("id") or ""),
                "playlist": str(entry.get("playlist_title") or ""),
                "title": str(entry.get("title") or entry.get("name") or "Untitled item"),
                "json": rendered[:6000],
                "json_truncated": len(rendered) > 6000,
                "csv": (
                    track_csv_preview(entry)
                    if category == "playlist_tracks"
                    else csv_preview(entry)
                ),
                "checkpoint": message == "checkpoint saved",
            }
        atomic_json(progress_path, {
            "category": category,
            "count": count,
            "total": total,
            "message": message,
            "latest_item": latest,
        })
        last_write = now

    report = export_profile(profile_url, directory, update, force)
    return json.dumps(report, ensure_ascii=False)


def get_snapshots(output_dir: str) -> str:
    return json.dumps(list_snapshots(Path(output_dir)), ensure_ascii=False)


def compare_snapshots(output_dir: str) -> str:
    return json.dumps(compare_latest_snapshots(Path(output_dir)), ensure_ascii=False)


def delete_snapshots(output_dir: str) -> None:
    delete_snapshot_history(Path(output_dir))

"""Progress adapter for the Android app; all extraction stays in exporter.py."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from exporter import atomic_json, csv_preview, export_profile


def run_export(profile_url: str, output_dir: str, force: bool = False) -> str:
    directory = Path(output_dir)
    progress_path = directory / "mobile-progress.json"
    last_write = 0.0

    def update(category: str, count: int, message: str, entry: dict[str, Any] | None = None) -> None:
        nonlocal last_write
        now = time.monotonic()
        if entry is not None and count % 5 != 0 and now - last_write < 1:
            return
        latest = None
        if entry is not None:
            rendered = json.dumps(entry, ensure_ascii=False, indent=2)
            latest = {
                "category": category,
                "count": count,
                "title": str(entry.get("title") or entry.get("name") or "Untitled item"),
                "json": rendered[:6000],
                "json_truncated": len(rendered) > 6000,
                "csv": csv_preview(entry),
                "checkpoint": message == "checkpoint saved",
            }
        atomic_json(progress_path, {
            "category": category,
            "count": count,
            "message": message,
            "latest_item": latest,
        })
        last_write = now

    report = export_profile(profile_url, directory, update, force)
    return json.dumps(report, ensure_ascii=False)

#!/usr/bin/env python3
"""Export publicly accessible SoundCloud likes and playlists; never logs in."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from yt_dlp import YoutubeDL
except ImportError:
    print("Missing dependency. Install it with: python -m pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)

UNSUPPORTED = {
    "followings": "The current yt-dlp SoundCloud extractor does not expose a followings collection. This exporter will not guess private/undocumented endpoints.",
}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def validate_profile_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() not in {"soundcloud.com", "www.soundcloud.com", "m.soundcloud.com"}:
        raise argparse.ArgumentTypeError("Enter a SoundCloud profile URL, e.g. https://soundcloud.com/artist")
    if len([part for part in parsed.path.split("/") if part]) != 1:
        raise argparse.ArgumentTypeError("Enter the profile URL only, not a /likes or /sets URL")
    return value


def extract_collection(ydl: YoutubeDL, url: str) -> dict[str, Any]:
    result = ydl.extract_info(url, download=False)
    if not isinstance(result, dict):
        raise RuntimeError("The extractor returned no collection metadata.")
    entries = result.get("entries")
    if entries is None:
        raise RuntimeError("SoundCloud did not return a collection. It may be private, blocked, or unsupported.")
    # yt-dlp normally returns a list here; materialize defensively before serializing.
    if not isinstance(entries, list):
        entries = list(entries)
    return {
        "collection_id": result.get("id"),
        "title": result.get("title"),
        "webpage_url": result.get("webpage_url") or url,
        "count": len(entries),
        "entries": entries,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Export public SoundCloud likes and playlists to local JSON without logging in.")
    parser.add_argument("url", nargs="?", help="Public SoundCloud profile URL")
    parser.add_argument("-o", "--output", default="soundcloud-export", help="Output directory (default: soundcloud-export)")
    parser.add_argument("--retry", action="store_true", help="Re-fetch categories even if already saved")
    args = parser.parse_args()

    raw_url = args.url or input("Public SoundCloud profile URL: ")
    try:
        profile = validate_profile_url(raw_url)
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "report.json"
    report: dict[str, Any] = {
        "profile_url": profile,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "categories": {},
        "note": "Only data publicly returned by SoundCloud/yt-dlp is included. This does not import data into another account.",
    }
    if report_path.exists() and not args.retry:
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("profile_url") != profile:
                report = {"profile_url": profile, "categories": {}, "note": "Only public data is included."}
        except (OSError, json.JSONDecodeError):
            pass

    ydl_options = {
        "quiet": False,
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

    # yt-dlp's maintained SoundCloud extractor handles linked-pagination for these pages.
    supported = {
        "likes": f"{profile}/likes",
        "playlists": f"{profile}/sets",
    }
    failures: list[dict[str, str]] = []
    with YoutubeDL(ydl_options) as ydl:
        for category, url in supported.items():
            target = output / f"{category}.json"
            if target.exists() and not args.retry:
                try:
                    cached = json.loads(target.read_text(encoding="utf-8"))
                    if cached.get("profile_url") == profile:
                        report.setdefault("categories", {})[category] = {"status": "saved", "count": cached.get("count"), "file": target.name, "resumed": True}
                        print(f"{category}: already saved ({cached.get('count', '?')} items); keeping checkpoint")
                        continue
                except (OSError, json.JSONDecodeError, AttributeError):
                    pass
            print(f"\nFetching public {category} from {url}")
            try:
                collection = extract_collection(ydl, url)
                collection["profile_url"] = profile
                atomic_json(target, collection)
                report.setdefault("categories", {})[category] = {"status": "complete", "count": collection["count"], "file": target.name}
                print(f"Saved {collection['count']} {category} to {target}")
            except Exception as exc:
                message = f"{type(exc).__name__}: {exc}"
                failures.append({"category": category, "url": url, "error": message})
                report.setdefault("categories", {})[category] = {"status": "failed", "error": message}
                print(f"Could not finish {category}: {message}", file=sys.stderr)
            report["exported_at"] = datetime.now(timezone.utc).isoformat()
            atomic_json(report_path, report)

    for category, reason in UNSUPPORTED.items():
        report.setdefault("categories", {})[category] = {"status": "unsupported", "reason": reason}
        print(f"\n{category}: not exported. {reason}")

    report["failures"] = failures
    report["exported_at"] = datetime.now(timezone.utc).isoformat()
    atomic_json(report_path, report)
    print(f"\nReport: {report_path}")
    print("No login was used. Only public items returned by SoundCloud were exported.")
    print("If a category failed, fix the reported access/network issue and rerun; completed JSON files are kept as checkpoints. Use --retry to re-fetch saved categories.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

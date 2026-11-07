import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).parents[1] / "android" / "app" / "src" / "main" / "python" / "mobile_export.py"
SPEC = importlib.util.spec_from_file_location("mobile_export", MODULE_PATH)
mobile_export = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(mobile_export)


class MobileExportTests(unittest.TestCase):
    def test_android_progress_adapter_writes_preview_and_returns_report(self):
        def fake_export(profile, output_dir, progress, force):
            progress("likes", 1, "pending next checkpoint", {"id": "track-1", "title": "First track"})
            progress("likes", 5, "checkpoint saved", {"id": "track-5", "title": "Fifth track"})
            return {"profile_url": profile, "categories": {"likes": {"status": "complete", "count": 5}}}

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(mobile_export, "export_profile", side_effect=fake_export):
                result = json.loads(mobile_export.run_export("https://soundcloud.com/artist", temporary))

            self.assertEqual(result["categories"]["likes"]["count"], 5)
            progress = json.loads((Path(temporary) / "mobile-progress.json").read_text(encoding="utf-8"))
            self.assertEqual(progress["category"], "likes")
            self.assertEqual(progress["count"], 5)
            self.assertEqual(progress["latest_item"]["title"], "Fifth track")
            self.assertIn("track-5", progress["latest_item"]["csv"])
            self.assertTrue(progress["latest_item"]["checkpoint"])

    def test_android_track_id_feed_records_every_track_even_when_preview_is_throttled(self):
        def fake_export(profile, output_dir, progress, force):
            for count in range(1, 8):
                progress("likes", count, "pending next checkpoint", {"id": f"track-{count}"})
            progress(
                "playlist_tracks",
                1,
                "track saved",
                {"id": "inside-1", "track_id": "inside-1", "playlist_title": "Set"},
                2,
            )
            return {"profile_url": profile, "categories": {}}

        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(mobile_export, "export_profile", side_effect=fake_export):
                mobile_export.run_export("https://soundcloud.com/artist", temporary)

            events = [
                json.loads(line)
                for line in (Path(temporary) / "mobile-track-ids.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(events), 8)
            self.assertEqual(events[0], {"category": "likes", "id": "track-1"})
            self.assertEqual(events[-1], {"category": "playlist_tracks", "id": "inside-1"})

    def test_android_track_id_feed_seeds_saved_likes_and_playlist_tracks(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "likes.json").write_text(json.dumps({
                "entries": [{"id": "like-1"}],
            }), encoding="utf-8")
            (directory / "playlist_tracks.json").write_text(json.dumps({
                "entries": [{"track_id": "set-1", "id": "set-1"}],
            }), encoding="utf-8")
            with patch.object(
                mobile_export,
                "export_profile",
                return_value={"profile_url": "https://soundcloud.com/artist", "categories": {}},
            ):
                mobile_export.run_export("https://soundcloud.com/artist", temporary)

            events = [
                json.loads(line)
                for line in (directory / "mobile-track-ids.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events, [
                {"category": "likes", "id": "like-1"},
                {"category": "playlist_tracks", "id": "set-1"},
            ])

    def test_android_track_id_feed_does_not_seed_completed_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "likes.json").write_text(json.dumps({
                "complete": True,
                "entries": [{"id": "old-like"}],
            }), encoding="utf-8")
            progress_path = directory / "mobile-progress.json"
            progress_path.write_text(json.dumps({"category": "old-category"}), encoding="utf-8")

            with patch.object(
                mobile_export,
                "export_profile",
                return_value={"profile_url": "https://soundcloud.com/artist", "categories": {}},
            ):
                mobile_export.run_export("https://soundcloud.com/artist", temporary)

            self.assertEqual((directory / "mobile-track-ids.jsonl").read_text(encoding="utf-8"), "")
            self.assertFalse(progress_path.exists())


if __name__ == "__main__":
    unittest.main()

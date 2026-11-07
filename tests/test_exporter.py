import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exporter import (
    compare_latest_snapshots,
    create_snapshot,
    delete_snapshot_history,
    export_category,
    export_playlist_tracks,
    export_profile,
    list_snapshots,
    normalize_profile_url,
)


class FakeYoutubeDL:
    entries = []

    def __init__(self, options):
        self.options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, url, download):
        return {"id": "public-collection", "title": "Public collection", "entries": self.entries}


class ExporterTests(unittest.TestCase):
    def test_normalizes_profile_url_and_rejects_non_profile_urls(self):
        self.assertEqual(
            normalize_profile_url("  https://www.soundcloud.com/artist/  "),
            "https://soundcloud.com/artist",
        )
        for value in (
            "https://soundcloud.com/",
            "https://soundcloud.com/artist/likes",
            "https://soundcloud.com.evil.example/artist",
            "https://soundcloud.com/artist?next=elsewhere",
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_profile_url(value)

    def test_resume_deduplicates_saved_entries_and_completes_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "likes.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": False,
                "entries": [{"id": "one"}],
            }), encoding="utf-8")
            FakeYoutubeDL.entries = [{"id": "one"}, {"id": "two"}]
            progress = []

            with patch("exporter.YoutubeDL", FakeYoutubeDL):
                result = export_category(
                    "https://soundcloud.com/artist",
                    "likes",
                    output_dir,
                    lambda *args: progress.append(args),
                )

            self.assertTrue(result["complete"])
            self.assertEqual([entry["id"] for entry in result["entries"]], ["one", "two"])
            self.assertEqual(result["count"], 2)
            self.assertTrue(progress)
            with (output_dir / "likes.csv").open(encoding="utf-8-sig", newline="") as stream:
                csv_rows = list(csv.DictReader(stream))
            self.assertEqual([row["id"] for row in csv_rows], ["one", "two"])
            state = json.loads((output_dir / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["categories"]["likes"]["status"], "complete")

    def test_csv_rows_include_metadata_and_are_updated_while_items_are_processed(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            FakeYoutubeDL.entries = [
                {"id": "track-1", "title": "First track", "webpage_url": "https://soundcloud.com/artist/track"},
            ]
            progress = []

            def on_progress(*args):
                progress.append(args)
                if len(args) == 5 and args[3] is not None:
                    with (output_dir / "likes.csv").open(encoding="utf-8-sig", newline="") as stream:
                        self.assertEqual(len(list(csv.DictReader(stream))), 1)

            with patch("exporter.YoutubeDL", FakeYoutubeDL):
                result = export_category(
                    "https://soundcloud.com/artist",
                    "likes",
                    output_dir,
                    on_progress,
                )

            self.assertTrue(result["complete"])
            with (output_dir / "likes.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["id"], "track-1")
            self.assertEqual(rows[0]["url"], "https://soundcloud.com/artist/track")
            self.assertEqual(progress[-1][3]["title"], "First track")
            self.assertEqual(progress[-1][2], "checkpoint saved")

    def test_refetch_does_not_preserve_stale_checkpoint_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "likes.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{"id": "old"}],
            }), encoding="utf-8")
            FakeYoutubeDL.entries = [{"id": "new"}]

            with patch("exporter.YoutubeDL", FakeYoutubeDL):
                result = export_category(
                    "https://soundcloud.com/artist", "likes", output_dir, lambda *args: None, force=True
                )

            self.assertEqual([entry["id"] for entry in result["entries"]], ["new"])

    def test_new_snapshot_refreshes_completed_collection_without_stale_items(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "likes.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{"id": "old"}],
            }), encoding="utf-8")
            FakeYoutubeDL.entries = [{"id": "current"}]

            with patch("exporter.YoutubeDL", FakeYoutubeDL):
                result = export_category(
                    "https://soundcloud.com/artist", "likes", output_dir, lambda *args: None
                )

            self.assertEqual([entry["id"] for entry in result["entries"]], ["current"])
            self.assertTrue(result["complete"])

    def test_failed_collection_is_saved_as_incomplete_checkpoint(self):
        class FailingYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url, download):
                def entries():
                    yield {"id": "saved"}
                    raise OSError("network interrupted")

                return {"entries": entries()}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with patch("exporter.YoutubeDL", FailingYoutubeDL):
                with self.assertRaisesRegex(OSError, "network interrupted"):
                    export_category(
                        "https://soundcloud.com/artist", "likes", output_dir, lambda *args: None
                    )

            saved = json.loads((output_dir / "likes.json").read_text(encoding="utf-8"))
            self.assertFalse(saved["complete"])
            self.assertEqual([entry["id"] for entry in saved["entries"]], ["saved"])

    def test_temporary_metadata_timeout_retries_and_completes(self):
        class RecoveringYoutubeDL(FakeYoutubeDL):
            attempts = 0

            def extract_info(self, url, download):
                type(self).attempts += 1
                if type(self).attempts == 1:
                    raise RuntimeError(
                        "Unable to download JSON metadata: The read operation timed out"
                    )
                return {"id": "collection", "entries": [{"id": "track"}]}

        with tempfile.TemporaryDirectory() as temporary:
            progress = []
            with patch("exporter.YoutubeDL", RecoveringYoutubeDL), patch("exporter.time.sleep"):
                result = export_category(
                    "https://soundcloud.com/artist",
                    "likes",
                    Path(temporary),
                    lambda *args: progress.append(args),
                )

            self.assertTrue(result["complete"])
            self.assertEqual(result["count"], 1)
            self.assertEqual(RecoveringYoutubeDL.attempts, 2)
            self.assertTrue(any("retrying" in event[2] for event in progress))

    def test_nontransient_collection_error_is_not_retried(self):
        class InvalidCollectionYoutubeDL(FakeYoutubeDL):
            attempts = 0

            def extract_info(self, url, download):
                type(self).attempts += 1
                raise RuntimeError("SoundCloud returned no public collection")

        with tempfile.TemporaryDirectory() as temporary:
            with patch("exporter.YoutubeDL", InvalidCollectionYoutubeDL), patch("exporter.time.sleep"):
                with self.assertRaisesRegex(RuntimeError, "no public collection"):
                    export_category(
                        "https://soundcloud.com/artist",
                        "likes",
                        Path(temporary),
                        lambda *args: None,
                    )

            self.assertEqual(InvalidCollectionYoutubeDL.attempts, 1)

    def test_timeout_after_partial_page_retries_without_duplicate_rows(self):
        class InterruptedYoutubeDL(FakeYoutubeDL):
            attempts = 0

            def extract_info(self, url, download):
                type(self).attempts += 1
                if type(self).attempts == 1:
                    def entries():
                        yield {"id": "saved"}
                        raise TimeoutError("The read operation timed out")
                    return {"entries": entries()}
                return {"entries": [{"id": "saved"}, {"id": "new"}]}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with patch("exporter.YoutubeDL", InterruptedYoutubeDL), patch("exporter.time.sleep"):
                result = export_category(
                    "https://soundcloud.com/artist",
                    "likes",
                    output_dir,
                    lambda *args: None,
                )

            self.assertTrue(result["complete"])
            self.assertEqual([entry["id"] for entry in result["entries"]], ["saved", "new"])
            with (output_dir / "likes.csv").open(encoding="utf-8-sig", newline="") as stream:
                self.assertEqual([row["id"] for row in csv.DictReader(stream)], ["saved", "new"])

    def test_rejects_unsupported_category(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "Unsupported category"):
                export_category(
                    "https://soundcloud.com/artist", "followings", Path(temporary), lambda *args: None
                )

    def test_expands_public_playlists_and_writes_track_snapshot_and_csv(self):
        class PlaylistYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url, download):
                if url.endswith("/sets/my-list"):
                    return {
                        "playlist_count": 2,
                        "entries": [
                            {"id": "track-1", "title": "First", "url": "https://soundcloud.com/a/one"},
                            {"id": "track-2", "title": "Second", "url": "https://soundcloud.com/a/two"},
                        ],
                    }
                return {"entries": self.entries}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "playlists.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{
                    "id": "playlist-1",
                    "title": "My list",
                    "webpage_url": "https://soundcloud.com/artist/sets/my-list",
                    "track_count": 2,
                }],
            }), encoding="utf-8")
            progress = []
            with patch("exporter.YoutubeDL", PlaylistYoutubeDL):
                result = export_playlist_tracks(
                    "https://soundcloud.com/artist",
                    output_dir,
                    lambda *args: progress.append(args),
                )

            self.assertTrue(result["complete"])
            self.assertEqual([entry["track_id"] for entry in result["entries"]], ["track-1", "track-2"])
            self.assertTrue(any(
                event[0] == "playlist_tracks" and event[3] and event[3]["id"] == "track-1"
                for event in progress
            ))
            with (output_dir / "playlist_tracks.csv").open(encoding="utf-8-sig", newline="") as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual([row["track_id"] for row in rows], ["track-1", "track-2"])
            self.assertEqual(rows[0]["playlist_title"], "My list")

    def test_playlist_track_resume_deduplicates_checkpoint_entries(self):
        class PlaylistYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url, download):
                return {"entries": [{"id": "track-1"}, {"id": "track-2"}]}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "playlists.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{
                    "id": "playlist-1",
                    "title": "My list",
                    "url": "https://soundcloud.com/artist/sets/my-list",
                }],
            }), encoding="utf-8")
            (output_dir / "playlist_tracks.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": False,
                "entries": [{
                    "playlist_id": "playlist-1",
                    "playlist_title": "My list",
                    "track_id": "track-1",
                    "id": "track-1",
                }],
            }), encoding="utf-8")

            with patch("exporter.YoutubeDL", PlaylistYoutubeDL):
                result = export_playlist_tracks(
                    "https://soundcloud.com/artist", output_dir, lambda *args: None
                )

            self.assertEqual([entry["track_id"] for entry in result["entries"]], ["track-1", "track-2"])
            self.assertEqual(result["count"], 2)

    def test_new_snapshot_refreshes_completed_playlist_tracks(self):
        class PlaylistYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url, download):
                return {"entries": [{"id": "current-track"}]}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "playlists.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{
                    "id": "playlist-1",
                    "title": "My list",
                    "url": "https://soundcloud.com/artist/sets/my-list",
                }],
            }), encoding="utf-8")
            (output_dir / "playlist_tracks.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{
                    "playlist_id": "playlist-1",
                    "playlist_title": "My list",
                    "track_id": "old-track",
                    "id": "old-track",
                }],
            }), encoding="utf-8")

            with patch("exporter.YoutubeDL", PlaylistYoutubeDL):
                result = export_playlist_tracks(
                    "https://soundcloud.com/artist", output_dir, lambda *args: None
                )

            self.assertEqual([entry["track_id"] for entry in result["entries"]], ["current-track"])
            self.assertTrue(result["complete"])

    def test_playlist_expansion_rejects_non_soundcloud_playlist_urls(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            (output_dir / "playlists.json").write_text(json.dumps({
                "profile_url": "https://soundcloud.com/artist",
                "complete": True,
                "entries": [{
                    "id": "playlist-1",
                    "title": "External",
                    "url": "https://soundcloud.com.evil.example/playlist",
                }],
            }), encoding="utf-8")
            with patch("exporter.YoutubeDL", FakeYoutubeDL):
                with self.assertRaisesRegex(RuntimeError, "public SoundCloud URL"):
                    export_playlist_tracks(
                        "https://soundcloud.com/artist", output_dir, lambda *args: None
                    )

    def test_snapshot_history_compares_and_clears_without_deleting_current_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            report = {
                "profile_url": "https://soundcloud.com/artist",
                "categories": {
                    name: {"status": "complete"}
                    for name in ("likes", "playlists", "playlist_tracks")
                },
            }
            (output_dir / "likes.json").write_text(json.dumps({
                "entries": [{"id": "old-track"}],
            }), encoding="utf-8")
            create_snapshot(output_dir, report)
            (output_dir / "likes.json").write_text(json.dumps({
                "entries": [{"id": "new-track"}],
            }), encoding="utf-8")
            create_snapshot(output_dir, report)

            comparison = compare_latest_snapshots(output_dir)

            self.assertEqual(len(list_snapshots(output_dir)), 2)
            self.assertEqual(comparison["categories"]["likes"]["added_ids"], ["new-track"])
            self.assertEqual(comparison["categories"]["likes"]["removed_ids"], ["old-track"])
            delete_snapshot_history(output_dir)
            self.assertEqual(list_snapshots(output_dir), [])
            self.assertTrue((output_dir / "likes.json").is_file())

    def test_incomplete_snapshot_categories_are_not_compared_as_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            report = {
                "profile_url": "https://soundcloud.com/artist",
                "categories": {
                    "likes": {"status": "complete"},
                    "playlists": {"status": "failed"},
                    "playlist_tracks": {"status": "failed"},
                },
            }
            (output_dir / "likes.json").write_text(json.dumps({"entries": [{"id": "like-1"}]}), encoding="utf-8")
            (output_dir / "playlists.json").write_text(json.dumps({"entries": [{"id": "old-list"}]}), encoding="utf-8")
            create_snapshot(output_dir, report)
            report["categories"] = {
                "likes": {"status": "complete"},
                "playlists": {"status": "complete"},
                "playlist_tracks": {"status": "complete"},
            }
            (output_dir / "playlists.json").write_text(json.dumps({"entries": [{"id": "new-list"}]}), encoding="utf-8")
            create_snapshot(output_dir, report)

            comparison = compare_latest_snapshots(output_dir)

            self.assertFalse(comparison["categories"]["playlists"]["available"])
            self.assertIn("incomplete", comparison["categories"]["playlists"]["reason"])

    def test_playlist_tracks_are_not_expanded_after_playlist_list_failure(self):
        class PlaylistFailureYoutubeDL(FakeYoutubeDL):
            requested_urls = []

            def extract_info(self, url, download):
                self.requested_urls.append(url)
                if url.endswith("/sets"):
                    raise ValueError("playlist refresh failed")
                return {"entries": []}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with patch("exporter.YoutubeDL", PlaylistFailureYoutubeDL):
                report = export_profile(
                    "https://soundcloud.com/artist", output_dir, lambda *args: None
                )

            self.assertEqual(report["categories"]["playlists"]["status"], "failed")
            self.assertEqual(report["categories"]["playlist_tracks"]["status"], "failed")
            self.assertIn("did not complete", report["categories"]["playlist_tracks"]["error"])
            self.assertFalse(any(url.endswith("/sets/my-list") for url in PlaylistFailureYoutubeDL.requested_urls))

    def test_profile_export_archives_snapshots_and_expands_playlist_tracks(self):
        class ProfileYoutubeDL(FakeYoutubeDL):
            def extract_info(self, url, download):
                if url.endswith("/likes"):
                    return {"playlist_count": 1, "entries": [{"id": "like-1", "title": "Liked"}]}
                if url.endswith("/sets"):
                    return {"playlist_count": 1, "entries": [{
                        "id": "playlist-1",
                        "title": "List",
                        "webpage_url": "https://soundcloud.com/artist/sets/list",
                    }]}
                return {"entries": [{"id": "inside-1", "title": "Inside playlist"}]}

        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            with patch("exporter.YoutubeDL", ProfileYoutubeDL):
                report = export_profile(
                    "https://soundcloud.com/artist", output_dir, lambda *args: None
                )

            self.assertEqual(report["categories"]["playlist_tracks"]["count"], 1)
            self.assertEqual(len(list_snapshots(output_dir)), 1)
            self.assertEqual(report["snapshot_id"], list_snapshots(output_dir)[0]["snapshot_id"])
            self.assertTrue((output_dir / "playlist_tracks.json").is_file())


if __name__ == "__main__":
    unittest.main()

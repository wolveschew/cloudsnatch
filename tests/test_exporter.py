import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from exporter import export_category, normalize_profile_url


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
                if len(args) == 4:
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


if __name__ == "__main__":
    unittest.main()

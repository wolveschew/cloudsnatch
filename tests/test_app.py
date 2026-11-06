import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app as app_module


class AppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app_module.app.config["TESTING"] = True
        app_module.app.config["OUTPUT_DIR"] = self.temp_dir.name
        with app_module._lock:
            app_module._job.update({
                "running": False,
                "profile_url": None,
                "status": "idle",
                "categories": {},
                "error": None,
                "report": None,
                "latest_item": None,
            })
        self.client = app_module.app.test_client()

    def tearDown(self):
        with app_module._lock:
            app_module._job["running"] = False
        self.temp_dir.cleanup()

    def test_homepage_loads_local_export_ui_and_settings(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"SoundSnatch", response.data)
        self.assertIn(b"Latest collection item", response.data)
        self.assertIn(b"Open folder", response.data)
        self.assertIn(b"Following lists", response.data)
        self.assertIn(b"Appearance settings", response.data)
        self.assertIn(b"Public metadata only", response.data)

    def test_export_rejects_invalid_profile_url(self):
        response = self.client.post("/api/export", json={"url": "https://example.com/artist"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("SoundCloud profile", response.json["error"])

    def test_export_rejects_non_boolean_retry_setting(self):
        response = self.client.post(
            "/api/export",
            json={"url": "https://soundcloud.com/artist", "retry": "false"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("true or false", response.json["error"])

    def test_status_restores_saved_report_for_the_ui(self):
        output = Path(self.temp_dir.name)
        report = {"profile_url": "https://soundcloud.com/artist", "categories": {"likes": {"status": "complete"}}}
        (output / "report.json").write_text(json.dumps(report), encoding="utf-8")

        response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["report"], report)
        self.assertEqual(response.json["categories"], report["categories"])

    def test_downloads_only_allowlisted_archive_files(self):
        output = Path(self.temp_dir.name)
        (output / "likes.json").write_text("{}", encoding="utf-8")

        with self.client.get("/api/files/likes.json") as response:
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/files/unknown.json").status_code, 404)

    def test_account_exports_use_separate_username_folders(self):
        first = app_module.account_output_dir("https://soundcloud.com/artist-one")
        second = app_module.account_output_dir("https://soundcloud.com/artist-two")

        self.assertNotEqual(first, second)
        self.assertEqual(first.parent, second.parent)
        self.assertTrue(first.name.startswith("artist-one-"))
        self.assertTrue(second.name.startswith("artist-two-"))
        self.assertTrue(first.is_relative_to(Path(self.temp_dir.name)))

    def test_open_folder_creates_and_opens_only_the_validated_account_path(self):
        with patch.object(app_module, "open_folder") as open_folder:
            response = self.client.post(
                "/api/open-folder",
                json={"url": "https://soundcloud.com/artist"},
            )

        self.assertEqual(response.status_code, 200)
        folder = Path(response.json["path"])
        self.assertTrue(folder.is_dir())
        self.assertEqual(folder, app_module.account_output_dir("https://soundcloud.com/artist"))
        open_folder.assert_called_once_with(folder)

    def test_open_folder_reports_operating_system_failures(self):
        with patch.object(app_module, "open_folder", side_effect=OSError("file manager unavailable")):
            response = self.client.post(
                "/api/open-folder",
                json={"url": "https://soundcloud.com/artist"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertIn("file manager unavailable", response.json["error"])

    def test_status_exposes_the_latest_json_and_csv_write(self):
        app_module.update_progress(
            "likes",
            1,
            "pending next checkpoint",
            {"id": "track-1", "title": "First track"},
        )

        response = self.client.get("/api/status")

        self.assertEqual(response.json["latest_item"]["category"], "likes")
        self.assertIn('"title": "First track"', response.json["latest_item"]["json"])
        self.assertIn("track-1", response.json["latest_item"]["csv"])

    def test_open_folder_rejects_non_profile_urls(self):
        response = self.client.post("/api/open-folder", json={"url": "https://example.com/artist"})

        self.assertEqual(response.status_code, 400)

    def test_existing_exports_are_copied_to_the_matching_account_folder(self):
        profile_url = "https://soundcloud.com/artist"
        legacy = Path(self.temp_dir.name)
        for name in ("likes.json", "report.json", "state.json"):
            (legacy / name).write_text(json.dumps({"profile_url": profile_url}), encoding="utf-8")

        target = app_module.migrate_legacy_account(profile_url)

        self.assertTrue((target / "likes.json").is_file())
        self.assertTrue((target / "report.json").is_file())
        self.assertTrue((target / "state.json").is_file())
        self.assertTrue((legacy / "likes.json").is_file())

    def test_appearance_settings_persist_in_the_local_data_directory(self):
        defaults = self.client.get("/api/settings")
        self.assertEqual(defaults.json, {"accent": "orange", "compact": False})

        saved = self.client.post("/api/settings", json={"accent": "blue", "compact": True})

        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json, {"accent": "blue", "compact": True})
        self.assertEqual(self.client.get("/api/settings").json, saved.json)
        self.assertTrue((Path(self.temp_dir.name) / "settings.json").is_file())

    def test_appearance_settings_reject_invalid_values(self):
        response = self.client.post("/api/settings", json={"accent": "invalid", "compact": "true"})

        self.assertEqual(response.status_code, 400)

    def test_invalid_saved_appearance_settings_fall_back_to_defaults(self):
        settings_path = Path(self.temp_dir.name) / "settings.json"
        settings_path.write_text(json.dumps({"accent": [], "compact": 1}), encoding="utf-8")

        response = self.client.get("/api/settings")

        self.assertEqual(response.json, {"accent": "orange", "compact": False})

    def test_export_job_exposes_category_results(self):
        report = {
            "categories": {
                "likes": {"status": "complete", "count": 2, "file": "likes.json"},
                "playlists": {"status": "failed", "error": "temporarily unavailable"},
                "followings": {"status": "unsupported", "reason": "Not supported."},
            }
        }
        with patch.object(app_module, "export_profile", return_value=report):
            response = self.client.post("/api/export", json={"url": "https://soundcloud.com/artist"})
            self.assertEqual(response.status_code, 200)
            deadline = time.monotonic() + 2
            status = None
            while time.monotonic() < deadline:
                status = self.client.get("/api/status").json
                if not status["running"]:
                    break
                time.sleep(0.01)

        self.assertIsNotNone(status)
        self.assertFalse(status["running"])
        self.assertEqual(status["categories"], report["categories"])


if __name__ == "__main__":
    unittest.main()

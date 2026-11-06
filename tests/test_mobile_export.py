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


if __name__ == "__main__":
    unittest.main()

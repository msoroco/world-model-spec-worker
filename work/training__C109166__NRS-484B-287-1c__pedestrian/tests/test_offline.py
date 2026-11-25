import json
from pathlib import Path
import unittest
from runner import check_config
from original_saved import required

class ExactCrossingOffline(unittest.TestCase):
    def test_selected_capture_profile(self):
        config = json.loads(Path("config.json").read_text())
        result = check_config(config)
        self.assertEqual(result["frames"], 600)
        self.assertEqual(result["camera_count"], 4)
        self.assertFalse(result["native_executed"])

    def test_missing_original_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "Missing required source: controls-original.jsonl"):
            required(Path.cwd(), "controls-original.jsonl")

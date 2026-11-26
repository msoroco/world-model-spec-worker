import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import build_construction


class ConstructionPackageTests(unittest.TestCase):
    def test_shared_package_binds_every_case_and_original_sources(self):
        config, measurement, construction = build_construction.build()
        self.assertEqual(len(config["supported_case_ids"]), 9)
        self.assertEqual(config["selected_case_id"], construction["case_id"])
        self.assertEqual(config["duration_s"] * config["rate_hz"], 240)
        self.assertEqual(construction["recording_description"], config["case"]["recording_description"])
        files = {item["path"]: item["content"] for item in construction["files"]}
        self.assertEqual(files["runner.py"], (ROOT / "runner.py").read_text())
        self.assertEqual(json.loads(files["config.json"]), config)
        self.assertEqual(json.loads(files["measurement-contract.json"]), measurement)
        self.assertEqual(set(measurement["requirements"][0]["inputs"]),
                         {"walker-body-history.jsonl", "signal-history.jsonl",
                          "device-history.jsonl", "video_frames.jsonl", "scene.json",
                          "camera-frame-joins.jsonl", "overview.mkv", "approach.mkv",
                          "reference_corner.mkv", "driver_reference.mkv"})

    def test_missing_mandatory_channel_rejected(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        plan["observations"].append({"name": "unrecorded_original_channel", "mandatory": True})
        original = Path.read_text

        def altered(path, *args, **kwargs):
            if Path(path) == ROOT / "case-plan.json":
                return json.dumps(plan)
            return original(path, *args, **kwargs)

        with patch.object(Path, "read_text", altered):
            with self.assertRaisesRegex(ValueError, "lack recorded channels"):
                build_construction.build()


if __name__ == "__main__":
    unittest.main()

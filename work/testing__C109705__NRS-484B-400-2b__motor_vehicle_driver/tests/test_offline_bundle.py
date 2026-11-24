"""Validate the four exact source-hashed left-turn diagnostic bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_four_exact_centerline_settings(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        expected = {row["case_id"]: row for row in plan["cases"]}
        self.assertEqual({row["case_id"] for row in manifest["cases"]}, set(expected))
        self.assertEqual({row["departure_centerline_kind"] for row in expected.values()},
                         {"mapped", "source_derived_imaginary"})
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                source = (ROOT / row["construction"]).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), row["construction_sha256"])
                construction = json.loads(source)
                self.assertEqual(construction["case_id"], row["case_id"])
                files = {item["path"]: item["content"] for item in construction["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["departure_centerline_kind"], expected[row["case_id"]]["departure_centerline_kind"])
                self.assertEqual(config["departure_position_target"], expected[row["case_id"]]["departure_position_target"])
                self.assertEqual(config["plan_sha256"], hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                self.assertEqual(config["cameras"], ["dash", "front", "left", "right"])
                self.assertEqual(config["frame_count"], 900)
                self.assertEqual(files["construction.py"], (ROOT / "construction.py").read_text())
                self.assertEqual(files["saved_delivery.py"], (ROOT / "saved_delivery.py").read_text())


if __name__ == "__main__":
    unittest.main()

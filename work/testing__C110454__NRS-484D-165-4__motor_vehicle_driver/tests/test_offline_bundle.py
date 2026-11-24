"""Validate the three exact source-hashed selected headlamp bundles."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_exact_modes_and_embedded_sources(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        expected = {row["case_id"]: row["requested_headlamp_mode"] for row in plan["cases"]}
        self.assertEqual({row["case_id"] for row in manifest["cases"]}, set(expected))
        self.assertEqual(set(expected.values()), {"unlit", "low_beam", "high_beam"})
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                source = (ROOT / row["construction"]).read_bytes()
                self.assertEqual(hashlib.sha256(source).hexdigest(), row["construction_sha256"])
                construction = json.loads(source)
                self.assertEqual(construction["case_id"], row["case_id"])
                files = {item["path"]: item["content"] for item in construction["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["requested_headlamp_mode"], expected[row["case_id"]])
                self.assertEqual(config["plan_sha256"], hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                self.assertEqual([camera['name'] for camera in config["cameras"]],
                                 ["overview", "approach", "reference_corner", "driver_reference"])
                self.assertFalse(construction['diagnostic_only'])
                self.assertEqual(config["rate_hz"], 20)
                self.assertEqual(config["frame_count"], 900)
                self.assertEqual(files["lamp_probe.py"], (ROOT / "lamp_probe.py").read_text())
                self.assertEqual(files["native_capture.py"], (ROOT / "native_capture.py").read_text())


if __name__ == "__main__":
    unittest.main()

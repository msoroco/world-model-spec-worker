"""Validate exact bicycle red-signal bundle inventory and source hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_five_exact_variants_and_sources(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {row["case_id"] for row in plan["cases"]})
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                data = (ROOT / row["construction"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["construction_sha256"])
                bundle = json.loads(data)
                self.assertEqual(bundle["case_id"], row["case_id"])
                files = {item["path"]: item["content"] for item in bundle["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["case_suffix"], row["case_id"].removeprefix(ROOT.name + "__"))
                self.assertEqual(config["plan_sha256"], hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                self.assertEqual(config["cameras"], ["overview", "approach", "reference_corner", "driver_reference"])
                self.assertEqual(config["rate_hz"], 20)
                self.assertEqual(config["frame_count"], 900)
                self.assertEqual(files["signal_trial.py"], (ROOT / "signal_trial.py").read_text())
                self.assertEqual(files["saved_attempt.py"], (ROOT / "saved_attempt.py").read_text())


if __name__ == "__main__":
    unittest.main()

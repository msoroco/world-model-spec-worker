"""Validate all exact diagnostic right-pass bundles and their source hashes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_exact_variants_and_sources(self):
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        plan = json.loads((ROOT / "case-plan.json").read_text())
        expected = {row["case_id"]: row["draft_variables"]["controller"]["target"] for row in plan["cases"]}
        self.assertEqual({row["case_id"] for row in manifest["cases"]}, set(expected))
        self.assertEqual(set(expected.values()), {"left_signal", "left_turn", "neither"})
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                data = (ROOT / row["construction"]).read_bytes()
                self.assertEqual(hashlib.sha256(data).hexdigest(), row["construction_sha256"])
                bundle = json.loads(data)
                self.assertEqual(bundle["case_id"], row["case_id"])
                files = {item["path"]: item["content"] for item in bundle["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["target_behavior_request"], expected[row["case_id"]])
                self.assertEqual(config["plan_sha256"], hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                self.assertEqual(config["cameras"], ["front", "rear", "left", "right"])
                self.assertEqual(config["rate_hz"], 20)
                self.assertEqual(config["frame_count"], 900)
                self.assertEqual(files["pass_right_route.py"], (ROOT / "pass_right_route.py").read_text())
                self.assertEqual(files["pass_right_audit.py"], (ROOT / "pass_right_audit.py").read_text())


if __name__ == "__main__":
    unittest.main()

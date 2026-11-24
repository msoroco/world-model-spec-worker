"""Check the source-bound five-case offline construction inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class OfflineBundleTests(unittest.TestCase):
    def test_all_exact_cases_and_source_hashes(self):
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
                files = {entry["path"]: entry["content"] for entry in bundle["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["selected_case_id"], row["case_id"])
                self.assertEqual(config["plan_sha256"], hashlib.sha256(files["case-plan.json"].encode()).hexdigest())
                self.assertEqual(config["cameras"], ["overview", "approach", "reference_corner", "driver_reference"])
                self.assertEqual(config["frame_count"], 900)
                self.assertEqual(config["rate_hz"], 20)
                self.assertEqual(files["geometry.py"], (ROOT / "geometry.py").read_text())
                self.assertEqual(files["native_walking.py"], (ROOT / "native_walking.py").read_text())
                self.assertEqual(files["native_source_packet.py"], (ROOT / "native_source_packet.py").read_text())
                self.assertEqual(files["native_readback.py"], (ROOT / "native_readback.py").read_text())


if __name__ == "__main__":
    unittest.main()

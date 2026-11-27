"""Check the root handoff selects the two distinct exact U-turn attempts."""

import json
import unittest
from pathlib import Path


PKG = Path(__file__).resolve().parents[1]


class RootPackageTest(unittest.TestCase):
    def test_exact_case_coverage_and_comparison_isolation(self):
        cfg = json.loads((PKG / "config.json").read_text())
        manifest = json.loads((PKG / "execution-manifest.json").read_text())
        plan = json.loads((PKG / "case-plan.json").read_text())
        selected = {entry["case_id"] for entry in manifest["cases"]}
        self.assertEqual(set(cfg["supported_case_ids"]), selected)
        self.assertEqual({case["case_id"] for case in plan["cases"]}, selected)
        requests = []
        configs = []
        for entry in manifest["cases"]:
            bundle = json.loads((PKG / entry["construction"]).read_text())
            files = {row["path"]: row["content"] for row in bundle["files"]}
            requests.append(json.loads(files["request.json"]))
            configs.append(json.loads(files["config.json"]))
        self.assertEqual({r["requested_crossing_x_m"] for r in requests}, {0, 10})
        self.assertEqual({r["source_map"] for r in requests}, {requests[0]["source_map"]})
        self.assertEqual({tuple((camera["name"], camera["width"], camera["height"])
                          for camera in c["cameras"]) for c in configs},
                         {tuple((camera["name"], camera["width"], camera["height"])
                          for camera in configs[0]["cameras"])})
        self.assertEqual({c["duration_s"] for c in configs}, {30})


if __name__ == "__main__":
    unittest.main()

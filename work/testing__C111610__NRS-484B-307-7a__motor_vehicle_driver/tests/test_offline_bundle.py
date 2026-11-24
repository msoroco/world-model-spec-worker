"""Check exact arrow bundles and their source-bound comparison variables."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import unittest

from build_offline_draft import CAMERAS, SOURCES, VARIANTS


HERE = Path(__file__).resolve().parents[1]
AID = HERE.name


class OfflineBundleTests(unittest.TestCase):
    def test_each_exact_case_and_source(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
        self.assertEqual(len(manifest["cases"]), len(VARIANTS))
        self.assertEqual({x["case_id"] for x in manifest["cases"]},
                         {x["case_id"] for x in plan["cases"]})
        source_cases = {x["case_id"]: x for x in plan["cases"]}
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                path = HERE / row["construction"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["construction_sha256"])
                data = json.loads(path.read_text())
                self.assertEqual(data["case_id"], row["case_id"])
                self.assertTrue(data["diagnostic_only"])
                files = {x["path"]: x["content"] for x in data["files"]}
                config = json.loads(files["config.json"])
                self.assertEqual(config["construction_plan"], source_cases[row["case_id"]]["construction"])
                self.assertEqual(config["cameras"], list(CAMERAS))
                self.assertEqual((config["rate_hz"], config["frame_count"], config["duration_s"]),
                                 (20, 900, 45))
                for name in SOURCES + ("case-plan.json",):
                    self.assertEqual(files[name], (HERE / name).read_text())

    def test_five_distinct_source_plans(self):
        cases = {x["case_suffix"]: x["construction"] for x in json.loads((HERE / "case-plan.json").read_text())["cases"]}
        self.assertEqual(set(cases), set(VARIANTS))
        self.assertEqual(cases["arrow_clear"]["participant"], "none")
        self.assertEqual(cases["arrow_ped_crosswalk"]["participant"], "pedestrian in adjacent crosswalk")
        self.assertEqual(cases["arrow_ped_intersection"]["participant"], "pedestrian in intersection")
        self.assertEqual(cases["arrow_vehicle_intersection"]["participant"], "other vehicle in intersection")
        self.assertEqual(cases["arrow_concurrent_movement"]["movement"], "concurrent indication movement")
        self.assertTrue(all(x["signal"].startswith("official flashing yellow turn arrow") for x in cases.values()))


if __name__ == "__main__":
    unittest.main()

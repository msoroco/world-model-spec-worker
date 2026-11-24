"""Verify all planned encounters materialize as exact, source-gated bundles."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import unittest

from encounter import CASES
from native_acquisition import CAMERAS


HERE = Path(__file__).resolve().parents[1]
AID = HERE.name


class OfflineBundleTests(unittest.TestCase):
    def test_all_exact_constructions(self):
        manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual(manifest["assignment_id"], AID)
        self.assertEqual({row["case_id"] for row in manifest["cases"]},
                         {row["case_id"] for row in plan["cases"]})
        self.assertEqual(len(manifest["cases"]), len(CASES))
        specs = {case.case_id: asdict(case) for case in CASES}
        for row in manifest["cases"]:
            with self.subTest(case=row["case_id"]):
                path = HERE / row["construction"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row["construction_sha256"])
                construction = json.loads(path.read_text())
                self.assertEqual(construction["case_id"], row["case_id"])
                self.assertTrue(construction["diagnostic_only"])
                files = {file["path"]: file["content"] for file in construction["files"]}
                config = json.loads(files["config.json"])
                suffix = row["case_id"].removeprefix(AID + "__")
                self.assertEqual(config["case_spec"], specs[suffix])
                self.assertEqual(config["cameras"], list(CAMERAS))
                self.assertEqual((config["rate_hz"], config["frame_count"], config["duration_s"]),
                                 (20, 900, 45))
                self.assertEqual(files["case-plan.json"], (HERE / "case-plan.json").read_text())
                for name in ("encounter.py", "native_acquisition.py", "site_binding.py",
                             "saved_audit.py", "media_audit.py"):
                    self.assertEqual(files[name], (HERE / name).read_text())

    def test_controlled_variations(self):
        specs = {case.case_id: asdict(case) for case in CASES}
        for left, right, changed in (
            ("person_north_early", "person_north_late", {"case_id", "crossing_release_s"}),
            ("person_south_early", "person_south_late", {"case_id", "crossing_release_s"}),
            ("person_north_early", "person_south_early", {"case_id", "approach"}),
            ("property_near", "property_far", {"case_id"}),
            ("premises_person_early", "premises_person_late", {"case_id", "crossing_release_s"}),
        ):
            with self.subTest(left=left, right=right):
                actual = {key for key in specs[left] if specs[left][key] != specs[right][key]}
                self.assertEqual(actual, changed)
        self.assertEqual(specs["person_north_early"]["public_access_basis"], "highway")
        self.assertEqual(specs["premises_person_early"]["public_access_basis"],
                         "public_access_premises")


if __name__ == "__main__":
    unittest.main()

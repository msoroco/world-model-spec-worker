import copy
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_crest_opendrive import check_source_geometry, grade
from site_construction import load_site


class CrestOpenDriveSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = PACKAGE / "native-map-plan"
        cls.road = (cls.root / "crest-road.xodr").read_text()

    def test_all_four_sites_bind_driving_lane_and_grade_source(self):
        rows = json.loads((self.root / "source-review.json").read_text())["sites"]
        self.assertEqual(len(rows), 4)
        for row in rows:
            path = PACKAGE / row["path"]
            with self.subTest(path=path.name):
                site = json.loads(path.read_text())
                self.assertTrue(check_source_geometry(self.road, site))
                self.assertEqual(site["source_status"], "diagnostic_fixture")
                self.assertEqual(site["camera_poses"]["driver_reference"], [1, 0, 1.5, 0, 0, 0])
                for name in ("overview", "approach", "reference_corner"):
                    pose = site["camera_poses"][name]
                    self.assertGreater(pose[2], grade(pose[0]))

    def test_grade_lane_and_hash_mismatch_are_rejected(self):
        site = json.loads((self.root / "approach_to_crest__occluded_approach_b.json").read_text())
        changed = copy.deepcopy(site)
        changed["incoming_lanes"]["approach_b"]["stations"][1]["xyz_m"][2] += 1
        with self.assertRaisesRegex(ValueError, "Site station differs"):
            check_source_geometry(self.road, changed)
        changed = copy.deepcopy(site)
        changed["map_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            check_source_geometry(self.road, changed)
        changed_road = self.road.replace('name="C129731 planned crest road"',
                                         'name="C129731 changed crest road"')
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            check_source_geometry(changed_road, site)


if __name__ == "__main__":
    unittest.main()

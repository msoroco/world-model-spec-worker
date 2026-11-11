import copy
import json
import sys
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))

from build_curve_opendrive import check_source_geometry


class CurveOpenDriveSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = PACKAGE / "native-map-plan"
        cls.road = (cls.root / "curve-road.xodr").read_text()

    def test_three_probes_and_both_occluded_directions_bind_source(self):
        rows = json.loads((self.root / "curve-source-review.json").read_text())["sites"]
        self.assertEqual(len(rows), 6)
        for row in rows:
            site = json.loads((PACKAGE / row["path"]).read_text())
            with self.subTest(name=row["name"]):
                self.assertTrue(check_source_geometry(self.road, site))
                self.assertEqual(site["source_status"], "diagnostic_fixture")
                self.assertEqual(site["incoming_lanes"]["approach_a"]["stations"][-1]
                                 ["distance_to_turn_m"], 180)
                self.assertEqual(site["incoming_lanes"]["approach_b"]["stations"][-1]
                                 ["distance_to_turn_m"], 180)

    def test_source_curve_lane_and_digest_mutations_are_rejected(self):
        site = json.loads((self.root / "curve_at_500ft__occluded_approach_b.json").read_text())
        changed = copy.deepcopy(site)
        changed["incoming_lanes"]["approach_b"]["stations"][1]["xyz_m"][1] += 2
        with self.assertRaisesRegex(ValueError, "station differs"):
            check_source_geometry(self.road, changed)
        changed = copy.deepcopy(site)
        changed["map_source"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Source hash differs"):
            check_source_geometry(self.road, changed)
        source = self.road.replace('curvature="0.00078125"', 'curvature="0.001"')
        with self.assertRaisesRegex(ValueError, "curvature changed"):
            check_source_geometry(source, site)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from alternate_route import CASES
from source_gated_sweeps import prepare
from test_reviewed_route_scene import ReviewedRouteSceneTest, write


class SourceGatedSweepTest(unittest.TestCase):
    def setUp(self):
        ReviewedRouteSceneTest.setUp(self)

    def sweep_packet(self):
        ref = ReviewedRouteSceneTest.packet(self, CASES[0])
        site_path = self.root / "site.json"
        site = json.loads(site_path.read_text())
        site["reviewed_control_feasibility"] = {
            "ego_speed_min_mps": 3, "ego_speed_max_mps": 7,
            "source": "diagnostic fake control packet"}
        site["reviewed_alternate_opportunities"] = [{
            "entry_lead_m": lead, "source": "diagnostic fake route source",
            "restriction_source": "diagnostic fake restriction source",
            "alternate_route_xy": [[0, 0], [10, 0], [20, lead]]}
            for lead in (40.0, 60.0, 80.0)]
        return write(site_path, site)

    def test_six_exact_source_gated_engineering_plans(self):
        ref = self.sweep_packet()
        plans = prepare(self.root, ref)
        self.assertEqual(len(plans), 6)
        self.assertEqual([p["requested_ego_speed_mps"] for p in plans[:3]], [4, 6, 5])
        self.assertEqual([p["requested_alternate_entry_lead_m"] for p in plans[3:]],
                         [40, 80, 60])
        self.assertTrue(all(p["legal_judgment"] is None for p in plans))
        self.assertTrue(all(p["possible_route_judgment"] is None for p in plans[3:]))

    def test_missing_original_feasibility_rejected(self):
        ref = self.sweep_packet()
        site_path = self.root / "site.json"
        site = json.loads(site_path.read_text())
        site["reviewed_control_feasibility"].pop("source")
        ref = write(site_path, site)
        with self.assertRaisesRegex(ValueError, "physical speed range missing"):
            prepare(self.root, ref)
        site["reviewed_control_feasibility"]["source"] = "fake"
        site["reviewed_alternate_opportunities"].pop()
        ref = write(site_path, site)
        with self.assertRaisesRegex(ValueError, "entry geometry and spacing missing"):
            prepare(self.root, ref)

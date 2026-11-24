import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from path_observation import ASSIGNMENT, measure
from path_route import select_route


class PathPackageTests(unittest.TestCase):
    def packet(self):
        return {"assignment_id": ASSIGNMENT, "original_trace_id": "synthetic-only",
                "ego_device_type": "electric_scooter", "ego_actor_id": "rider-a",
                "roadway_id": "road-a", "path_id": "path-a",
                "path_designation_source": "synthetic-sign-a",
                "path_adjacent_to_roadway": True, "sidewalk_status": "absent",
                "path_usability_status": "unresolved",
                "path_condition_source": "synthetic-condition-a",
                "access_restrictions_source": "synthetic-access-a",
                "frames": [{"time_s": i * 0.05, "ego_body_on_roadway": False,
                            "ego_body_on_designated_path": True} for i in range(3)]}

    def site(self):
        return {"assignment_id": ASSIGNMENT, "map_id": "synthetic-map",
                "roadway_id": "road-a", "path_id": "path-a",
                "path_designation_source": "synthetic-sign-a",
                "path_adjacent_to_roadway": True, "sidewalk_status": "absent",
                "path_usability_status": "unresolved",
                "path_polygon": [[0, 0], [8, 0], [8, 2], [0, 2]],
                "roadway_polygon": [[0, 3], [8, 3], [8, 7], [0, 7]],
                "route_candidates": {"path": [[1, 1], [7, 1]],
                                     "roadway": [[1, 5], [7, 5]],
                                     "escape": [[1, 1], [7, 5]]}}

    def run_packet(self, packet):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "original.json"
            p.write_text(json.dumps(packet), encoding="utf-8")
            return measure(p)

    def run_site(self, site, candidate, target):
        with tempfile.TemporaryDirectory(dir=os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) as d:
            p = Path(d) / "site.json"
            p.write_text(json.dumps(site), encoding="utf-8")
            return select_route(p, candidate, target)

    def test_path_ride_keeps_usability_unresolved(self):
        r = self.run_packet(self.packet())
        self.assertTrue(r["path_use_observed"])
        self.assertFalse(r["roadway_use_observed"])
        self.assertEqual(r["path_usability_status"], "unresolved")

    def test_roadway_ride_detected(self):
        p = self.packet()
        p["frames"][1]["ego_body_on_roadway"] = True
        self.assertTrue(self.run_packet(p)["roadway_use_observed"])

    def test_all_covered_devices(self):
        for device in ("bicycle", "electric_bicycle", "electric_scooter"):
            p = self.packet()
            p["ego_device_type"] = device
            self.assertEqual(self.run_packet(p)["ego_device_type"], device)

    def test_missing_access_source_rejected(self):
        p = self.packet()
        del p["access_restrictions_source"]
        with self.assertRaisesRegex(ValueError, "access"):
            self.run_packet(p)

    def test_path_and_roadway_routes_constructed(self):
        self.assertEqual(self.run_site(self.site(), "path", "path")["target_facility"], "path")
        self.assertEqual(self.run_site(self.site(), "roadway", "roadway")["target_facility"], "roadway")

    def test_route_leaving_path_rejected(self):
        with self.assertRaisesRegex(ValueError, "leaves"):
            self.run_site(self.site(), "escape", "path")

    def test_sidewalk_cell_mismatch_rejected(self):
        s = self.site()
        s["sidewalk_status"] = "present"
        with self.assertRaisesRegex(ValueError, "sidewalk"):
            self.run_site(s, "path", "path")


if __name__ == "__main__":
    unittest.main()

"""CPU fixtures for sourced one-way protected-lane construction and measurement."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lane_use import CASES, construct, measure_original, validate_site


HERE = Path(__file__).resolve().parents[1]


def site():
    return {"cell_id": "C147339", "layout": "one_way_multilane",
            "map_source_sha256": "diagnostic-map", "lane_source_sha256": "diagnostic-lane",
            "highway_source_sha256": "diagnostic-highway",
            "public_maintenance_source_sha256": "diagnostic-maintenance",
            "public_vehicle_access_source_sha256": "diagnostic-access",
            "ego_blueprint_source_sha256": "diagnostic-ego",
            "motorcycle_class_source_sha256": "diagnostic-motorcycle",
            "moped_class_source_sha256": "diagnostic-moped",
            "motorcycle_exclusion_review_sha256": "diagnostic-exclusions",
            "same_one_way_direction": True,
            "lane_ids": {"protected": "lane-1", "adjacent": "lane-2"},
            "protected_lane_center_xy": [0, 0], "lane_lateral_unit_xy": [0, 1],
            "protected_lane_width_m": 3.5, "ego_width_m": 2.0, "protected_width_m": .8,
            "protected_route": {"source_sha256": "diagnostic-protected-route",
                                "waypoints_xy": [[0, 0], [40, 0]]},
            "ego_routes": {name: {"source_sha256": "diagnostic-" + name,
                                  "waypoints_xy": [[0, 3.5], [40, target]]}
                           for name, target in (("adjacent", 3.5), ("edge", 1.9),
                                                ("deep", .8))}}


class Adapter:
    def __init__(self, fail_ego=False):
        self.calls = []; self.fail_ego = fail_ego

    def spawn_vehicle(self, position, role, kind):
        self.calls.append(("spawn", role, kind, tuple(position)))
        return None if role == "ego" and self.fail_ego else role

    def set_route(self, actor, route, target_speed_mps):
        self.calls.append(("route", actor, target_speed_mps))

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


class LaneUseTests(unittest.TestCase):
    def rows(self, case):
        target = {"adjacent": 3.5, "edge": 1.9, "deep": .8}[case.ego_path]
        return [{"original_frame": 200 + i, "time_s": i / 20,
                 "source_sha256": "diagnostic-frame",
                 "ego_pose_sha256": "diagnostic-ego-pose",
                 "protected_pose_sha256": "diagnostic-protected-pose",
                 "map_source_sha256": "diagnostic-map",
                 "lane_source_sha256": "diagnostic-lane",
                 "highway_source_sha256": "diagnostic-highway",
                 "ego_id": "ego-1", "protected_id": "protected-1",
                 "ego_kind": "motor_vehicle", "protected_kind": case.protected_kind,
                 "ego_xy": [10, target], "protected_xy": [12, 0],
                 "protected_speed_mps": 6 if case.protected_driven else 0}
                for i in range(900)]

    def test_all_exact_cases_construct_and_measure(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual({row["case_id"].removeprefix(HERE.name + "__") for row in plan["cases"]},
                         {case.case_id for case in CASES})
        self.assertEqual(len(plan["comparisons"]), 4)
        measurements = {}
        for case in CASES:
            with self.subTest(case=case.case_id):
                adapter = Adapter(); built = construct(adapter, site(), case)
                self.assertEqual(adapter.calls[0][2], case.protected_kind)
                self.assertEqual(adapter.calls[2],
                                 ("route", "protected", 6 if case.protected_driven else 0))
                result = measure_original(self.rows(case), site(), case)
                self.assertEqual(result["frame_count"], 900)
                self.assertEqual(result["protected_driven_observed"], case.protected_driven)
                self.assertEqual(result["full_use_judgment"], "unresolved")
                self.assertIsNone(result["legal_judgment"])
                measurements[case.case_id] = result["terminal_mean_ego_body_intrusion_m"]
        self.assertEqual(measurements["motorcycle_adjacent_clear"], 0)
        self.assertGreater(measurements["motorcycle_edge_encroach"], 0)
        self.assertGreater(measurements["motorcycle_deep_encroach"],
                           measurements["motorcycle_edge_encroach"])

    def test_site_and_original_source_rejections(self):
        specimen = site(); specimen["ego_routes"]["edge"]["waypoints_xy"][-1] = [40, 3.4]
        with self.assertRaisesRegex(ValueError, "isolate lane intrusion"):
            validate_site(specimen)
        specimen = site(); specimen["lane_ids"]["adjacent"] = "lane-1"
        with self.assertRaisesRegex(ValueError, "distinct one-way lanes"):
            validate_site(specimen)
        specimen = site(); specimen["motorcycle_class_source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "source missing"):
            validate_site(specimen)
        case = CASES[1]; rows = self.rows(case); rows[100]["map_source_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "site source changed"):
            measure_original(rows, site(), case)

    def test_motion_classification_and_frame_rejections(self):
        case = CASES[1]; rows = self.rows(case); rows[100]["protected_kind"] = "moped"
        with self.assertRaisesRegex(ValueError, "classification"):
            measure_original(rows, site(), case)
        rows = self.rows(case)
        for row in rows:
            row["protected_speed_mps"] = 0
        with self.assertRaisesRegex(ValueError, "motion differs"):
            measure_original(rows, site(), case)
        rows = self.rows(case); rows[10]["original_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame/time"):
            measure_original(rows, site(), case)
        rows = self.rows(case)
        for row in rows[-20:]:
            row["ego_xy"] = [10, 3.5]
        with self.assertRaisesRegex(ValueError, "did not enter"):
            measure_original(rows, site(), case)

    def test_spawn_failure_cleans_protected_vehicle(self):
        adapter = Adapter(fail_ego=True)
        with self.assertRaisesRegex(ValueError, "ego motor vehicle spawn failed"):
            construct(adapter, site(), CASES[0])
        self.assertEqual(adapter.calls[-1], ("destroy", "protected"))


if __name__ == "__main__":
    unittest.main()

"""CPU construction tests for the eight exact highway-side parking probes."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from parking import CASES, construct, measure_original, validate_site


HERE = Path(__file__).resolve().parents[1]


def site():
    return {
        "cell_id": "C135705", "layout": "narrow_road",
        "highway_status": "source_reviewed", "highway_source_sha256": "diagnostic-highway",
        "map_source_sha256": "diagnostic-map", "edge_source_sha256": "diagnostic-edge",
        "edge_point_xy": [0, 0], "roadward_unit_xy": [0, 1],
        "edge_vehicle_xy": [10, .7], "ego_side_xy": [10, 3.0],
        "ego_behind_xy": [20, .7], "ego_approach_xy": [0, 3.0],
        "approach_route_xy": [[0, 3.0], [5, 3.0], [10, 3.0]],
        "approach_route_source_sha256": "diagnostic-route",
        "ego_blueprint_source_sha256": "diagnostic-ego",
        "edge_blueprint_source_sha256": "diagnostic-edge-vehicle",
    }


class Adapter:
    def __init__(self, fail_ego=False):
        self.calls = []
        self.fail_ego = fail_ego

    def spawn_vehicle(self, xy, role):
        self.calls.append(("spawn", role, tuple(xy)))
        return None if role == "ego" and self.fail_ego else role

    def hold_vehicle(self, actor, activity):
        self.calls.append(("hold", actor, activity))

    def set_route(self, actor, route, target_xy):
        self.calls.append(("route", actor, tuple(target_xy)))

    def request_halt(self, actor, target_xy, activity):
        self.calls.append(("halt", actor, tuple(target_xy), activity))

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


class ParkingTests(unittest.TestCase):
    def original_rows(self, case):
        target = [20, .7] if case.endpoint == "behind_edge_vehicle" else [10, 3.0]
        return [{"original_frame": 100 + i, "time_s": i / 20,
                 "source_sha256": "diagnostic-actor-frame",
                 "highway_source_sha256": "diagnostic-highway",
                 "map_source_sha256": "diagnostic-map",
                 "edge_source_sha256": "diagnostic-edge",
                 "ego_control_source_sha256": "diagnostic-control",
                 "ego_id": "ego-1", "edge_vehicle_id": "edge-1",
                 "ego_xy": target, "edge_vehicle_xy": [10, .7],
                 "ego_speed_mps": 0.0, "edge_speed_mps": 0.0,
                 "exception_source_sha256": "diagnostic-exception"
                 if case.exception_probe else None} for i in range(900)]

    def test_all_exact_cases_spawn_and_request_distinct_endpoints(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual({row["case_id"].removeprefix(HERE.name + "__") for row in plan["cases"]},
                         {case.case_id for case in CASES})
        self.assertEqual(len(plan["comparisons"]), 7)
        for case in CASES:
            with self.subTest(case=case.case_id):
                adapter = Adapter()
                result = construct(adapter, site(), case)
                self.assertEqual(result["requested_activity"], case.activity)
                self.assertEqual(result["exception_probe"], case.exception_probe)
                self.assertEqual(adapter.calls[0][:2], ("spawn", "edge_vehicle"))
                self.assertEqual(adapter.calls[1], ("hold", "edge_vehicle", "park"))
                self.assertEqual(adapter.calls[2][:2], ("spawn", "ego"))
                target = [20, .7] if case.endpoint == "behind_edge_vehicle" else [10, 3.0]
                self.assertEqual(result["requested_endpoint_xy"], target)
                self.assertIn(("halt", "ego", tuple(target), case.activity), adapter.calls)
                self.assertIsNone(result["legal_judgment"])

    def test_source_and_actual_geometry_rejections(self):
        specimen = site()
        del specimen["edge_source_sha256"]
        with self.assertRaisesRegex(ValueError, "source missing"):
            validate_site(specimen)
        specimen = site(); specimen["ego_side_xy"] = [10, .8]
        with self.assertRaisesRegex(ValueError, "not highway side"):
            validate_site(specimen)
        specimen = site(); specimen["ego_behind_xy"] = [20, 3]
        with self.assertRaisesRegex(ValueError, "behind target"):
            validate_site(specimen)
        specimen = site(); specimen["approach_route_xy"] = [[1, 3], [10, 3]]
        with self.assertRaisesRegex(ValueError, "route"):
            validate_site(specimen)

    def test_failure_cleans_owned_edge_vehicle(self):
        adapter = Adapter(fail_ego=True)
        with self.assertRaisesRegex(ValueError, "ego vehicle spawn failed"):
            construct(adapter, site(), CASES[0])
        self.assertEqual(adapter.calls[-1], ("destroy", "edge_vehicle"))

    def test_original_relationship_for_all_exact_cases(self):
        for case in CASES:
            with self.subTest(case=case.case_id):
                result = measure_original(self.original_rows(case), site(), case)
                self.assertEqual(result["frame_count"], 900)
                self.assertEqual(result["first_original_frame"], 100)
                self.assertEqual(result["last_original_frame"], 999)
                self.assertIsNone(result["legal_judgment"])
                self.assertEqual(result["exception_judgment"], "unresolved")

    def test_original_geometry_clock_and_exception_rejections(self):
        rows = self.original_rows(CASES[0])
        for row in rows[-20:]:
            row["ego_xy"] = [10, .7]
        with self.assertRaisesRegex(ValueError, "highway side"):
            measure_original(rows, site(), CASES[0])
        rows = self.original_rows(CASES[0]); rows[10]["time_s"] += .1
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            measure_original(rows, site(), CASES[0])
        rows = self.original_rows(CASES[4])
        for row in rows:
            row["exception_source_sha256"] = None
        with self.assertRaisesRegex(ValueError, "exception context"):
            measure_original(rows, site(), CASES[4])
        rows = self.original_rows(CASES[0]); rows[-1]["ego_speed_mps"] = 2.0
        with self.assertRaisesRegex(ValueError, "requested halt"):
            measure_original(rows, site(), CASES[0])


if __name__ == "__main__":
    unittest.main()

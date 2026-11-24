"""Diagnostic CPU tests for exact trail-to-crossing pedestrian probes."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pedestrian_crossing import CASES, construct, measure_original, validate_site


HERE = Path(__file__).resolve().parents[1]


def site():
    destinations = {"curb": [10.8, 2.1], "sidewalk": [11, 1],
                    "safety_zone": [10.8, .5], "other_place": [11, 3]}
    return {"cell_id": "C143766", "actor": "pedestrian",
            "trail_source_sha256": "diagnostic-trail", "highway_source_sha256": "diagnostic-highway",
            "crossing_source_sha256": "diagnostic-crossing",
            "sidewalk_source_sha256": "diagnostic-sidewalk",
            "signal_source_sha256": "diagnostic-signal",
            "signal_facing_source_sha256": "diagnostic-facing",
            "signal_facing_pedestrian": True,
            "trail_route_xy": [[-2, 1], [-.1, 1]],
            "crossing_route_xy": [[0, 1], [5, 1], [10, 1]],
            "highway_polygon_xy": [[0, 0], [10, 0], [10, 2], [0, 2]],
            "destination_routes": {name: {"source_sha256": "diagnostic-" + name,
                                          "waypoints_xy": [[10, 1], point]}
                                   for name, point in destinations.items()},
            "safety_zone_provided_source_sha256": "diagnostic-zone",
            "other_place_safety_review_sha256": "diagnostic-other-review"}


class Adapter:
    def __init__(self, fail=False):
        self.calls = []; self.fail = fail

    def spawn_pedestrian(self, xy):
        self.calls.append(("spawn", tuple(xy)))
        return None if self.fail else "ped-1"

    def request_signal_schedule(self, **kwargs):
        self.calls.append(("signal", kwargs))

    def set_pedestrian_route(self, ped, route, **kwargs):
        self.calls.append(("route", ped, route, kwargs))

    def destroy(self, ped):
        self.calls.append(("destroy", ped))


class PedestrianCrossingTests(unittest.TestCase):
    def rows(self, case):
        entry_i = 80 if case.entry_phase == "walk" else 120
        arrival_i = 320 if case.arrival_phase == "steady" else 280
        target = site()["destination_routes"][case.destination]["waypoints_xy"][-1]
        rows = []
        for i in range(900):
            phase = "walk" if i < 100 else "flashing" if i < 300 else "steady"
            if i < entry_i:
                xy = [-1, 1]
            elif i >= arrival_i:
                xy = target
            else:
                progress = (i - entry_i) / (arrival_i - entry_i)
                xy = [.1 + progress * (target[0] - .1), 1 + progress * (target[1] - 1)]
            rows.append({"original_frame": 1000 + i, "time_s": i / 20,
                         "source_sha256": "diagnostic-frame",
                         "signal_readback_sha256": "diagnostic-display",
                         "pedestrian_pose_sha256": "diagnostic-pose",
                         "site_source_sha256": "diagnostic-signal",
                         "facing_source_sha256": "diagnostic-facing",
                         "pedestrian_id": "ped-1", "pedestrian_xy": xy,
                         "signal_phase": phase,
                         "countdown_visible": case.countdown if phase == "flashing" else False})
        return rows

    def test_all_exact_cases_construct_and_measure(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual({row["case_id"].removeprefix(HERE.name + "__") for row in plan["cases"]},
                         {case.case_id for case in CASES})
        self.assertEqual(len(plan["comparisons"]), 6)
        for case in CASES:
            with self.subTest(case=case.case_id):
                adapter = Adapter(); built = construct(adapter, site(), case)
                self.assertEqual(built["destination"], case.destination)
                self.assertEqual(adapter.calls[1][1]["countdown_during_flashing"], case.countdown)
                self.assertEqual(adapter.calls[2][3]["requested_entry_s"],
                                 4 if case.entry_phase == "walk" else 6)
                measured = measure_original(self.rows(case), site(), case)
                self.assertEqual(measured["entry_phase"], case.entry_phase)
                self.assertEqual(measured["arrival_phase"], case.arrival_phase)
                self.assertEqual(measured["frame_count"], 900)
                self.assertEqual(measured["prior_entry_lawfulness"], "unresolved")
                self.assertIsNone(measured["legal_judgment"])

    def test_route_and_source_rejections(self):
        specimen = site(); specimen["trail_route_xy"][-1] = [-5, 1]
        with self.assertRaisesRegex(ValueError, "does not connect"):
            validate_site(specimen)
        specimen = site(); specimen["destination_routes"]["sidewalk"]["source_sha256"] = ""
        with self.assertRaisesRegex(ValueError, "sourced destination"):
            validate_site(specimen)
        specimen = site(); specimen["signal_facing_pedestrian"] = False
        with self.assertRaisesRegex(ValueError, "does not face"):
            validate_site(specimen)

    def test_original_signal_timing_and_countdown_rejections(self):
        case = CASES[0]
        rows = self.rows(case); rows[150]["countdown_visible"] = True
        with self.assertRaisesRegex(ValueError, "countdown"):
            measure_original(rows, site(), case)
        rows = self.rows(case); rows[101]["original_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame/time"):
            measure_original(rows, site(), case)
        rows = self.rows(case); rows[120]["site_source_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "site changed"):
            measure_original(rows, site(), case)
        rows = self.rows(case); rows[100]["signal_phase"] = "steady"
        with self.assertRaisesRegex(ValueError, "transition"):
            measure_original(rows, site(), case)

    def test_spawn_failure(self):
        with self.assertRaisesRegex(ValueError, "spawn failed"):
            construct(Adapter(fail=True), site(), CASES[0])


if __name__ == "__main__":
    unittest.main()

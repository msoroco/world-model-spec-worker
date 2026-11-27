"""Exercise actual constructor calls and original-frame pass geometry on CPU fakes."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from school_pass import ASSIGNMENT, SOURCES, construct, measure_original, validate_scene
from test_school_timing import packet


def scene(name="active_beacon_pass"):
    source = {
        "case_id": ASSIGNMENT + "__" + name,
        "cell_id": "C261489", "law_id": "NRS-484B-363-4", "actor": "motor_vehicle_driver",
        "driver_id": "reviewed-driver", "ego_id": "ego-1", "target_id": "target-2",
        "ego_vehicle_class": "conventional_motor_vehicle",
        "target_vehicle_class": "conventional_motor_vehicle",
        "same_direction": True,
        "designated_zone_polygon_xy": [[0, -5], [100, -5], [100, 5], [0, 5]],
        "school_property_polygon_xy": [[0, 6], [100, 6], [100, 20], [0, 20]],
        "zone_designation_kind": "school_zone", "school_property_adjacency_reviewed": True,
        "ego_route_xy": [[10, 0], [30, 2], [50, 2], [70, 0]],
        "target_route_xy": [[20, 0], [40, 0], [60, 0]],
        "ego_route_lane_ids": [1, 2, 2, 1], "target_route_lane_ids": [1, 1, 1],
        "passing_lane_direction": "same_as_ego", "target_lane_direction": "same_as_ego",
        "pass_start_frame": 100, "pass_end_frame": 700,
        "pass_requested": name != "no_pass", "minimum_lateral_clearance_m": 1.0,
        "local_datetime": "2026-04-15T14:00:00-07:00",
        "timing_packet": packet("2026-04-15T14:00:00-07:00"),
    }
    source.update({key + "_source_sha256": str(i + 1).zfill(64) for i, key in enumerate(SOURCES)})
    if name == "school_not_in_session":
        source["timing_packet"]["school_in_session"] = False
    if name == "class_no_flash":
        source["timing_packet"]["lamp_state_samples"] = [
            {"original_frame": i, "yellow_lamps_on": [False, False]} for i in range(4)
        ]
    if name == "sign_without_operational_beacon":
        source["timing_packet"].update(zone_designated_by_operational_beacon=False,
                                       beacon_operational=False, sign_limit_active=False)
    if name == "outside_zone":
        source["ego_route_xy"] = [[10, 8], [30, 8], [50, 8], [70, 8]]
    for probe, stamp in {
        "after_end_29m": "2026-04-15T15:29:00-07:00",
        "after_end_30m": "2026-04-15T15:30:00-07:00",
        "after_end_31m": "2026-04-15T15:31:00-07:00",
        "before_start_31m": "2026-04-16T07:29:00-07:00",
        "before_start_30m": "2026-04-16T07:30:00-07:00",
        "before_start_29m": "2026-04-16T07:31:00-07:00",
    }.items():
        if name == probe:
            source["local_datetime"] = stamp
            source["timing_packet"]["local_datetime"] = stamp
    return source


def rows(site):
    result = []
    for i in range(900):
        p = (i - 100) / 600
        complete = site["pass_requested"]
        ego_progress = 15 + i * .07 + (p * 20 if complete else 0)
        target_progress = 25 + i * .07
        ego_y = 2 if 100 <= i <= 700 and complete else 0
        ego_x = 20 + i * .05
        target_x = 25 + i * .05
        if site["case_id"].endswith("outside_zone"):
            ego_y = 8
        row = {
            "original_frame": 10000 + i, "time_s": 1 + i / 20,
            "driver_id": site["driver_id"], "ego_id": site["ego_id"],
            "target_id": site["target_id"], "ego_xy": [ego_x, ego_y],
            "target_xy": [target_x, 0],
            "ego_route_progress_m": ego_progress,
            "target_route_progress_m": target_progress,
            "lateral_separation_m": abs(ego_y),
        }
        row.update({name + "_source_sha256": site[name + "_source_sha256"] for name in SOURCES})
        result.append(row)
    return result


class FakeAdapter:
    def __init__(self):
        self.calls = []
        self.beacon = {}

    def spawn_vehicle(self, identity, xy, vehicle_class):
        self.calls.append(("spawn", identity, tuple(xy), vehicle_class))
        return identity

    def set_route(self, actor, points, lanes):
        self.calls.append(("route", actor, len(points), tuple(lanes)))

    def set_pass_window(self, ego, target, start, end, requested):
        self.calls.append(("pass", ego, target, start, end, requested))

    def set_beacon(self, operational, alternating_flash):
        self.beacon = {"operational": operational, "alternating_flash": alternating_flash}
        self.calls.append(("beacon", operational, alternating_flash))

    def read_beacon(self):
        return self.beacon

    def destroy(self, actor):
        self.calls.append(("destroy", actor))


class PassTests(unittest.TestCase):
    def test_all_exact_case_sources_and_call_shapes(self):
        names = ("active_beacon_pass", "school_not_in_session", "after_end_29m",
                 "after_end_30m", "after_end_31m", "before_start_31m",
                 "before_start_30m", "before_start_29m", "class_no_flash",
                 "sign_without_operational_beacon", "no_pass", "outside_zone")
        for name in names:
            with self.subTest(name=name):
                site = scene(name)
                self.assertIsNone(validate_scene(site, site["case_id"])["legal_judgment"])
                adapter = FakeAdapter()
                result = construct(adapter, site, site["case_id"])
                self.assertEqual(result["owned"], ("ego-1", "target-2"))
                self.assertEqual(len([x for x in adapter.calls if x[0] == "route"]), 2)
                self.assertEqual(len([x for x in adapter.calls if x[0] == "pass"]), 1)

    def test_original_pass_and_no_pass(self):
        for name in ("active_beacon_pass", "no_pass", "outside_zone"):
            site = scene(name)
            measured = measure_original(rows(site), site, site["case_id"])
            self.assertEqual(measured["completed_pass"], name != "no_pass")
            self.assertEqual(measured["pass_inside_zone"], name != "outside_zone")
            self.assertIsNone(measured["legal_judgment"])

    def test_missing_original_source_rejected(self):
        site = scene()
        original = rows(site)
        del original[120]["map_geometry_source_sha256"]
        with self.assertRaisesRegex(ValueError, "original source changed"):
            measure_original(original, site, site["case_id"])

    def test_incomplete_pass_rejected(self):
        site = scene()
        original = rows(site)
        for row in original:
            row["ego_route_progress_m"] = row["target_route_progress_m"] - 5
        with self.assertRaisesRegex(ValueError, "not physically completed"):
            measure_original(original, site, site["case_id"])

    def test_wrong_way_passing_lane_rejected(self):
        site = scene()
        site["passing_lane_direction"] = "opposite"
        with self.assertRaisesRegex(ValueError, "surveyed same travel direction"):
            validate_scene(site, site["case_id"])


if __name__ == "__main__":
    unittest.main()

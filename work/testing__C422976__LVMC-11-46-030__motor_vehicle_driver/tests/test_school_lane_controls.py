"""CPU checks for real control calls and 49/50/51-foot engineering geometry."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("school_lane_controls", ROOT / "school_lane_controls.py")
CONTROLS = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = CONTROLS
SPEC.loader.exec_module(CONTROLS)


class Adapter:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args):
            self.calls.append((name, args))
        return record


class SchoolLaneControlTests(unittest.TestCase):
    def source(self):
        return {"source_kind": "reviewed_original_site", "opendrive_sha256": "a" * 64,
                "nearest_side_geometry_sha256": "b" * 64,
                "nearest_side_station_m": 100.0,
                "municipal_jurisdiction_source": "survey", "ego_approach_lane_id": -1,
                "school_lane_polygon_xy": [[0, 0], [1, 0], [1, 3], [0, 3]],
                "human_actor_source": "reviewed-actor", "device_actor_source": "reviewed-device",
                "child_actor_source": "reviewed-child", "vehicle_reference_point_source": "survey"}

    def test_every_exact_case_calls_distinct_native_controls(self):
        for variant in CONTROLS.VARIANTS:
            with self.subTest(variant=variant.suffix):
                adapter = Adapter()
                schedule = CONTROLS.apply_schedule(adapter, self.source(),
                                                    CONTROLS.ASSIGNMENT + "__" + variant.suffix)
                self.assertEqual([name for name, _ in adapter.calls],
                                 ["load_reviewed_map", "spawn_vehicle_in_lane", "spawn_children",
                                  "spawn_warning_actor", "attach_four_cameras", "install_schedule"])
                self.assertEqual(schedule["requested_release"], variant.release)
                self.assertEqual(schedule["requested_ego_response"], variant.response)

    def test_distance_targets_are_distinct_and_do_not_decide_law(self):
        stations = [CONTROLS.station_target_m(100, CONTROLS.VARIANTS[i]) for i in range(3)]
        self.assertAlmostEqual(stations[0], 100 - 51 * .3048)
        self.assertAlmostEqual(stations[1], 100 - 50 * .3048)
        self.assertAlmostEqual(stations[2], 100 - 49 * .3048)
        self.assertEqual(len(set(stations)), 3)
        self.assertEqual(CONTROLS.control_schedule(CONTROLS.VARIANTS[0], 100)["legal_judgment"],
                         "unresolved")

    def test_missing_source_and_unknown_case_rejected_before_native_calls(self):
        source = self.source()
        source.pop("nearest_side_geometry_sha256")
        adapter = Adapter()
        with self.assertRaisesRegex(ValueError, "nearest_side_geometry_sha256"):
            CONTROLS.apply_schedule(adapter, source,
                                    CONTROLS.ASSIGNMENT + "__human_warning_stop_51ft_go")
        self.assertEqual(adapter.calls, [])
        with self.assertRaisesRegex(ValueError, "unselected exact"):
            CONTROLS.exact_variant(CONTROLS.ASSIGNMENT + "__unknown")


if __name__ == "__main__":
    unittest.main()

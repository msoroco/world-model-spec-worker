"""CPU-only tests for source gating and engineering signal requests."""

from __future__ import annotations

import unittest
from pathlib import Path
import json
import os
import tempfile
from unittest.mock import patch

from native_site import validate
from signal_controller import METRES_PER_FOOT, request_right_signal
from native_capture_contract import CAMERAS, DIMENSIONS
from runner import execute


def site(district: str = "business") -> dict:
    packet = {
        "source_kind": "original_local_right_turn_site_inventory",
        "map_name": "reviewed-map", "ego_blueprint_id": "reviewed-vehicle",
        "district_kind": district, "maneuver": "right_turn",
        "freight_zone_actor_id": "reviewed-zone", "reviewer": "source-reviewer",
        "drive_speed_m_s": 4.0,
        "approach_start_xyz": [-120.0, 0.0, 0.0],
        "turn_vertex_xyz": [0.0, 0.0, 0.0],
        "outgoing_target_xyz": [0.0, -20.0, 0.0],
        "district_review": {"jurisdiction": "reviewed-jurisdiction",
                            "frontage_bounds": "reviewed-bounds",
                            "building_uses": "reviewed-use",
                            "reviewer": "source-reviewer"},
        "camera_rig_source": "reviewed-camera-rig",
        "camera_rigs": {name: {"relative_xyz": [0.0, 0.0, 2.0],
                               "relative_ypr_deg": [0.0, 0.0, 0.0],
                               "dimensions": list(DIMENSIONS[name])} for name in CAMERAS},
    }
    for key in ("highway_source", "district_source", "frontage_source",
                "building_use_source", "freight_zone_source", "route_source",
                "vehicle_source", "driver_source", "speed_source", "weather_source"):
        packet[key] = "reviewed-" + key
    return packet


class ConstructionTest(unittest.TestCase):
    def test_all_districts_validate_only_matching_right_turn(self) -> None:
        for district, case in (("business", "business_at_100ft"),
                               ("residential", "residence_at_100ft"),
                               ("other", "other_area_at_300ft")):
            with self.subTest(district=district):
                result = validate(site(district), case)
                self.assertEqual(result["district_kind"], district)
                self.assertLess(result["signed_turn_angle_deg"], -35)

    def test_source_and_route_rejections(self) -> None:
        original = site()
        for mutation in ({"source_kind": "authored-target"},
                         {"diagnostic_fixture": True},
                         {"district_source": ""},
                         {"camera_rigs": {}},
                         {"maneuver": "left_turn"},
                         {"drive_speed_m_s": 12.0},
                         {"approach_start_xyz": [-50.0, 0.0, 0.0]},
                         {"outgoing_target_xyz": [0.0, 20.0, 0.0]}):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    validate({**original, **mutation}, "business_at_100ft")

    def test_all_numeric_request_triples_remain_distinct(self) -> None:
        for prefix, threshold in (("business", 100), ("residence", 100),
                                  ("other_area", 300)):
            short = f"{prefix}_short"
            at = f"{prefix}_at_{threshold}ft"
            continuous = f"{prefix}_continuous"
            for case, start in ((short, threshold - 1), (at, threshold),
                                (continuous, threshold + 1)):
                with self.subTest(case=case):
                    self.assertTrue(request_right_signal(case, start * METRES_PER_FOOT,
                                                         4.0))
                    self.assertFalse(request_right_signal(case,
                                                          (start + 3) * METRES_PER_FOOT,
                                                          4.0))
        self.assertEqual(request_right_signal("business_continuous", 30.0, 4.0),
                         request_right_signal("business_weather_rain", 30.0, 4.0))

    def test_course_changed_and_bad_measurements_rejected(self) -> None:
        self.assertFalse(request_right_signal("business_continuous", 0.0, 4.0,
                                              course_changed=True))
        for case, remaining, speed in (("unknown", 2.0, 4.0),
                                       ("business_short", -1.0, 4.0),
                                       ("business_short", 2.0, float("nan"))):
            with self.assertRaises(ValueError):
                request_right_signal(case, remaining, speed)

    def test_reviewed_site_gate_runs_before_adapter_import(self) -> None:
        case = "testing__C412593__NRS-484B-413-2__motor_vehicle_driver__residence_continuous"
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temporary:
            root = Path(temporary)
            packet = root / "site.json"
            packet.write_text(json.dumps(site("residential")) + "\n")
            with patch("runner.importlib.import_module") as adapter:
                with self.assertRaisesRegex(ValueError, "site hash mismatch"):
                    execute(case, packet, "0" * 64, root, "carla_adapter", "127.0.0.1", 2000)
                adapter.assert_not_called()


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import railway_7b as rail


def source(case_name):
    authority, instruction, response = rail.CASES[case_name]
    site = {"law_id": rail.LAW, "cell_id": rail.CELL, "actor": rail.ACTOR,
            "layout": "paved_road", "maneuver": "cross_railway", "control": "traffic_control_device",
            "crossing": {"grade_crossing": True,
                         **{key: "original:" + key for key in (
                             "rail_geometry_ref", "road_geometry_ref", "approach_lane_ref",
                             "crossing_entry_ref", "crossing_exit_ref")}},
            "vehicle": {"driver_role": rail.ACTOR, "blueprint_id": "vehicle.test",
                        "blueprint_source_ref": "original:blueprint", "actor_id": 7,
                        "driver_identity_ref": "original:driver"},
            "device": {key: "original:" + key for key in (
                "actor_or_map_id", "device_type", "placement_ref", "erection_authority_ref",
                "traffic_purpose_ref", "governed_movement_ref", "instruction_source_ref")},
            "officer": {"actor_id": 8, "identity_ref": "original:officer",
                        "position_ref": "original:position", "direction_channel_ref": "original:gesture"},
            "case": {"name": case_name, "authority": authority,
                     "instruction": instruction, "response": response}}
    site["_packet_sha256"] = hashlib.sha256(json.dumps(site, sort_keys=True).encode()).hexdigest()
    return site


def frames(site, crossing=False):
    instruction = site["case"]["instruction"]
    authority = site["case"]["authority"]
    rows = []
    for frame in range(4):
        row = {"source_frame": frame, "time_s": frame / 20,
               "source_site_sha256": site["_packet_sha256"],
               "device_indication": instruction if authority == "device" else "clear",
               "officer_direction": instruction if authority == "officer" else None,
               "front_body_gap_to_entry_m": 5.0 - 2.0 * frame if crossing else 5.0,
               "rear_body_gap_to_exit_m": -10.0,
               "speed_mps": 2.0 if crossing else 0.0,
               "brake_applied": not crossing}
        row.update({key: "original:" + key for key in (
            "device_indication_source_ref", "device_instruction_source_ref",
            "governed_movement_source_ref", "body_source_ref", "control_source_ref",
            "crossing_geometry_source_ref", "officer_direction_source_ref")})
        rows.append(row)
    return rows


class SourceTests(unittest.TestCase):
    def test_six_case_site_and_response_join(self):
        for case_name in rail.CASES:
            with self.subTest(case_name=case_name):
                site = source(case_name)
                crossing = case_name.endswith("cross")
                result = rail.measure(site, frames(site, crossing))
                self.assertEqual(result["observed_crossing_entry"], crossing)
                self.assertEqual(result["observed_halt_before_entry"], not crossing)
                self.assertEqual(result["legal_judgment"], "unresolved")

    def test_officiality_and_source_are_required(self):
        site = source("device_stop_cross")
        del site["device"]["erection_authority_ref"]
        with self.assertRaisesRegex(ValueError, "officiality"):
            rail.measure(site, frames(site, True))
        site = source("officer_stop_cross")
        rows = frames(site, True)
        del rows[0]["officer_direction_source_ref"]
        with self.assertRaisesRegex(ValueError, "officer direction"):
            rail.measure(site, rows)

    def test_missing_frame_and_instruction_change_rejected(self):
        site = source("device_stop_cross")
        rows = frames(site, True)
        rows[2]["source_frame"] = 4
        with self.assertRaisesRegex(ValueError, "sequence"):
            rail.measure(site, rows)
        rows = frames(site, True)
        rows[2]["device_indication"] = "clear"
        with self.assertRaisesRegex(ValueError, "instruction not maintained"):
            rail.measure(site, rows)


if __name__ == "__main__":
    unittest.main()

"""Compare original school-zone U-turn captures with fixed geometry checks."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from school_uturn import CASES, measure_original


VARIABLES = {
    "children_presence": {"children_present", "children", "children_identity_source_sha256",
                          "children_location_source_sha256"},
    "school_session": {"school_session", "operation_window", "timing_packet",
                       "school_calendar_source_sha256", "school_operation_time_source_sha256"},
    "operation_half_hour": {"operation_window", "local_datetime", "timing_packet",
                            "local_clock_source_sha256", "school_operation_time_source_sha256"},
    "beacon_class_flash": {"beacon_flashing", "timing_packet", "beacon_state_source_sha256"},
    "sign_without_beacon": {"beacon_operational", "beacon_flashing",
                            "sign_limit_active", "timing_packet",
                            "beacon_configuration_source_sha256", "beacon_state_source_sha256",
                            "sign_instruction_source_sha256"},
}
FIXED = ("cell_id", "actor", "qualifying_vehicle", "highway", "driver_id",
         "vehicle_id", "crossing_zone_rect_m", "school_property_rect_m",
         "nonadjacent_street", "pupil_route_designated", "reversal_route_xy",
         "turn_start_frame", "turn_end_frame", "crossing_zone_designation_source_sha256",
         "crossing_zone_extent_source_sha256", "school_property_nonadjacency_source_sha256",
         "designated_pupil_route_source_sha256")


def audit(left: str | Path, right: str | Path, comparison: str) -> dict:
    if comparison not in VARIABLES:
        raise ValueError("unknown exact school-zone comparison")
    paths = [Path(left), Path(right)]
    raw = [path.read_bytes() for path in paths]
    packets = [json.loads(value) for value in raw]
    base = next(case for case in CASES if case.name == "children_active_zone")
    target_names = {"children_presence": "no_children",
                    "school_session": "school_not_in_session",
                    "operation_half_hour": "outside_operation_half_hour",
                    "beacon_class_flash": "beacon_class_no_flash",
                    "sign_without_beacon": "sign_limit_inactive"}
    cases = [base, next(case for case in CASES if case.name == target_names[comparison])]
    for packet, case in zip(packets, cases):
        if packet.get("case_id") != case.name or not packet.get("original_recording_id"):
            raise ValueError("original exact case/recording identity required")
        if not isinstance(packet.get("frames"), list) or not isinstance(packet.get("scene"), dict):
            raise ValueError("original scene and frames required")
        measure_original(packet.get("frames"), packet.get("scene"), case)
    scenes = [packet["scene"] for packet in packets]
    for key in FIXED:
        if scenes[0].get(key) is None or scenes[0][key] != scenes[1].get(key):
            raise ValueError("fixed original geometry/source differs: " + key)
    for key in ("children_present", "school_session", "operation_window",
                "beacon_operational", "beacon_flashing", "sign_limit_active"):
        if key not in VARIABLES[comparison] and scenes[0].get(key) != scenes[1].get(key):
            raise ValueError("undeclared exception state differs: " + key)
    return {"comparison_id": comparison, "case_ids": [packet["case_id"] for packet in packets],
            "original_sha256": [hashlib.sha256(value).hexdigest() for value in raw],
            "fixed_geometry_and_states_checked": True,
            "review_limit": "Source and motion isolation do not establish legal permission or accepted capture."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=tuple(VARIABLES), required=True)
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.left, args.right, args.comparison)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

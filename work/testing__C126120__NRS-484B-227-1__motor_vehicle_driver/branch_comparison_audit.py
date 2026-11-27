"""Independent source-bound audits for the added divided-roadway branches."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from uturn_audit import measure

PREFIX = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver__"
PAIRS = {
    "opening_vs_crossover_facility": ("opening_single", "crossover_candidate"),
    "opening_vs_intersection_facility": ("opening_single", "intersection_candidate"),
    "uturn_vs_right_roadway_continuation": ("opening_single", "right_roadway_no_turn"),
}
GEOMETRY_KEYS = (
    "opening_bounds_xy_m", "closed_divider_bounds_xy_m",
    "source_right_roadway_bounds_xy_m", "destination_right_roadway_bounds_xy_m",
    "opposite_non_right_roadway_bounds_xy_m", "source_right_roadway_id",
    "destination_right_roadway_id", "ego_actor_id", "divider_actor_ids",
    "authority_review_source_sha256",
)
FIXED_CONFIG_KEYS = (
    "law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
    "vehicle_blueprint_id",
)


def _read(path, digest):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("comparison original source hash mismatch: " + str(path))
    return json.loads(raw)


def audit(comparison_id, left_trace, left_hash, right_trace, right_hash,
          left_config, left_config_hash, right_config, right_config_hash):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison ID")
    left_suffix, right_suffix = PAIRS[comparison_id]
    configs = [_read(left_config, left_config_hash),
               _read(right_config, right_config_hash)]
    for config, suffix in zip(configs, (left_suffix, right_suffix)):
        if config.get("selected_case_id") != PREFIX + suffix:
            raise ValueError("comparison exact case identity differs")
    for key in FIXED_CONFIG_KEYS:
        if key == "vehicle_blueprint_id" and not configs[0].get(key):
            raise ValueError("fixed vehicle blueprint identity is absent")
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("fixed comparison config changed: " + key)
    left, right = _read(left_trace, left_hash), _read(right_trace, right_hash)
    a, b = measure(left), measure(right)
    context_a, context_b = left["context"], right["context"]
    if comparison_id.startswith("opening_vs_"):
        for key in GEOMETRY_KEYS:
            if context_a.get(key) != context_b.get(key):
                raise ValueError("fixed facility geometry or source changed: " + key)
        varying = {"opening_id", "crossing_kind", "map_source_sha256",
                   "reviewed_context_sha256"}
        for key in varying:
            if context_a.get(key) == context_b.get(key):
                raise ValueError("facility identity source did not vary: " + key)
        if not (a["engineering_crossing_observed"] and
                b["engineering_crossing_observed"] and
                a["destination_right_roadway_departure_observed"] and
                b["destination_right_roadway_departure_observed"]):
            raise ValueError("facility pair did not share measured U-turn crossing")
        differences = sorted(varying)
    else:
        varying = set()
        expected = {
            "u_turn_orientation_observed": (True, False),
            "source_right_roadway_all_frames": (False, True),
            "source_right_roadway_final_occupancy": (False, True),
            "destination_right_roadway_departure_observed": (True, False),
        }
        for key, values in expected.items():
            if (a[key], b[key]) != values:
                raise ValueError("measured continuation difference absent: " + key)
        differences = sorted(expected)
    for key in set(context_a) | set(context_b):
        if key not in varying and context_a.get(key) != context_b.get(key):
            raise ValueError("fixed comparison context changed: " + key)
    return {
        "comparison_id": comparison_id,
        "case_ids": [item["selected_case_id"] for item in configs],
        "declared_differences": differences,
        "original_source_sha256": {left_suffix: left_hash, right_suffix: right_hash},
        "fixed_config_sha256": {left_suffix: left_config_hash,
                                right_suffix: right_config_hash},
        "measurements": {"left": a, "right": b},
        "legal_verdict_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_id", choices=PAIRS)
    for name in ("left_trace", "left_hash", "right_trace", "right_hash",
                 "left_config", "left_config_hash", "right_config",
                 "right_config_hash"):
        parser.add_argument(name)
    args = parser.parse_args()
    print(json.dumps(audit(*(getattr(args, name) for name in
                            ("comparison_id", "left_trace", "left_hash",
                             "right_trace", "right_hash", "left_config",
                             "left_config_hash", "right_config",
                             "right_config_hash"))), sort_keys=True))


if __name__ == "__main__":
    main()

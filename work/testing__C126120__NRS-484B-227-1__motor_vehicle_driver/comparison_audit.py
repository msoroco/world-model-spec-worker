"""Source-hashed original-frame comparison for the three planned C126120 pairs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from uturn_audit import compare


PREFIX = "testing__C126120__NRS-484B-227-1__motor_vehicle_driver__"
PAIRS = {
    "continuous_vs_multiple_movement": ("opening_single", "opening_multiple",
                                        ["multiple_movement_observed"]),
    "opening_vs_closed_divider": ("opening_single", "closed_divider",
                                  ["engineering_crossing_observed"]),
    "right_roadway_departure": ("opening_single", "wrong_roadway",
                                ["destination_right_roadway_departure_observed"]),
}


def _load(path, expected_hash):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_hash:
        raise ValueError("comparison original source hash mismatch: " + str(path))
    return json.loads(raw)


def audit(comparison_id, left_trace, left_hash, right_trace, right_hash,
          left_config, left_config_hash, right_config, right_config_hash):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact comparison ID")
    left_suffix, right_suffix, differences = PAIRS[comparison_id]
    configs = [_load(left_config,left_config_hash), _load(right_config,right_config_hash)]
    for item,suffix in zip(configs,(left_suffix,right_suffix)):
        if item.get("selected_case_id") != PREFIX+suffix:
            raise ValueError("comparison exact case identity differs")
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
                "vehicle_blueprint_id"):
        if key == "vehicle_blueprint_id" and not configs[0].get(key):
            raise ValueError("fixed vehicle blueprint identity is absent")
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("fixed comparison config changed: " + key)
    left, right = _load(left_trace,left_hash), _load(right_trace,right_hash)
    measured = compare(left,right,differences)
    return {"comparison_id":comparison_id,
            "case_ids":[item["selected_case_id"] for item in configs],
            "declared_differences":differences,
            "original_source_sha256":{left_suffix:left_hash,right_suffix:right_hash},
            "fixed_config_sha256":{left_suffix:left_config_hash,right_suffix:right_config_hash},
            "measurements":measured,
            "legal_verdict_claimed":False}

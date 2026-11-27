"""Independent saved-source comparison of the selected obstruction pair.

This checks engineering isolation and response only. It cannot decide whether
stopping or parking would legally obstruct traffic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_obstruction import measure
from source_join import check as check_source_join

ASSIGNMENT = "training__C135702__NRS-484B-450-1k__motor_vehicle_driver"
PREFIX = ASSIGNMENT + "__selected_dacdf461__condition_"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError("Missing comparison source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _case(root: Path, suffix: str, source_kind: str) -> tuple[dict, list[dict], dict]:
    cfg_path = root / "config.json"
    if not cfg_path.is_file():
        raise ValueError("Missing comparison config")
    cfg = json.loads(cfg_path.read_text())
    if cfg.get("case_id") != PREFIX + suffix or cfg.get("law_id") != "NRS-484B-450-1k" or cfg.get("actor") != "motor_vehicle_driver":
        raise ValueError("Exact comparison case identity differs")
    check_source_join(root, source_kind)
    path = root / "native_samples.jsonl"
    rows = _rows(path)
    observed = measure(path, _sha(path))
    if any(row.get("obstruction_kind") != "physical_obstruction" for row in rows):
        raise ValueError("Physical obstruction source differs")
    return cfg, rows, observed


def audit(left: Path, right: Path, source_kind: str = "original_native") -> dict:
    left, right = Path(left), Path(right)
    cfg_a, rows_a, measured_a = _case(left, "a", source_kind)
    cfg_b, rows_b, measured_b = _case(right, "b", source_kind)
    fixed_config = ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "frames",
                    "vehicle_blueprint_id", "cameras", "passing_throttle",
                    "brake_station_x_m", "barrier_spawn_z_m")
    if any(cfg_a.get(name) != cfg_b.get(name) for name in fixed_config):
        raise ValueError("Comparison capture or controller policy differs")
    if cfg_a.get("park_y_m") == cfg_b.get("park_y_m"):
        raise ValueError("Comparison parked position was not varied")
    for index, (a, b) in enumerate(zip(rows_a, rows_b)):
        for key in ("road_xy_m", "obstruction_xy_m", "obstruction_kind",
                    "exceptions", "exception_source"):
            if a.get(key) != b.get(key):
                raise ValueError("Comparison fixed source differs at frame " + str(index) + ": " + key)
        if a.get("time_s") != b.get("time_s"):
            raise ValueError("Comparison timeline differs")
    if not measured_a["minimum_open_width_m"] < measured_b["minimum_open_width_m"]:
        raise ValueError("Measured transverse opening did not differ as authored")
    if not measured_a["minimum_open_width_m"] < measured_a["passing_body_width_m"]:
        raise ValueError("Narrow case did not measure a sub-body-width opening")
    if not measured_b["minimum_open_width_m"] > measured_b["passing_body_width_m"]:
        raise ValueError("Clear case did not measure a wider opening")
    return {"format": "c135702-source-comparison-audit-v1", "passed": True,
            "case_ids": [cfg_a["case_id"], cfg_b["case_id"]],
            "source_kind": source_kind, "fixed_conditions_checked": list(fixed_config) + [
                "road_xy_m", "obstruction_xy_m", "obstruction_kind",
                "exceptions", "exception_source", "time_s"],
            "declared_difference": "parked_vehicle_lateral_position_and_measured_traffic_response",
            "measurements": {"condition_a": measured_a, "condition_b": measured_b},
            "physical_causation_confirmed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition-a", type=Path, required=True)
    parser.add_argument("--condition-b", type=Path, required=True)
    parser.add_argument("--source-kind", choices=("original_native", "synthetic_cpu"),
                        default="original_native")
    args = parser.parse_args()
    print(json.dumps(audit(args.condition_a, args.condition_b, args.source_kind)))

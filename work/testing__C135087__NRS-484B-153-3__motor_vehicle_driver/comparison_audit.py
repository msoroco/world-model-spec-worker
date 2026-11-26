"""Reopen two original door episodes and enforce a controlled comparison."""
from __future__ import annotations

import json
from pathlib import Path

from door_measurement import _source, measure


def _read_attempt(root: Path, case_id: str, plan_path: Path):
    inventory = json.loads((root / "inventory.json").read_text())
    result = measure(root, inventory, case_id, plan_path)
    source = inventory["sources"]
    packets = {name: _source(root, source[name]) for name in source}
    return result, packets


def _values(packet, keys):
    return [{key: row[key] for key in keys} for row in packet["samples"]]


def audit_pair(left: Path, right: Path, comparison_id: str, plan_path: Path) -> dict:
    plan = json.loads(Path(plan_path).read_text())
    matches = [row for row in plan.get("comparisons", [])
               if row.get("comparison_id") == comparison_id]
    if len(matches) != 1 or len(matches[0].get("case_ids", [])) != 2:
        raise ValueError("unknown exact comparison")
    a, b = matches[0]["case_ids"]
    left_result, left_packets = _read_attempt(Path(left), a, plan_path)
    right_result, right_packets = _read_attempt(Path(right), b, plan_path)
    if left_packets["frame_map"].get("frames") != right_packets["frame_map"].get("frames"):
        raise ValueError("comparison original frame/time coverage differs")
    if left_packets["geometry"] != right_packets["geometry"]:
        raise ValueError("comparison narrow-road and loading geometry differs")
    path_fields = ("vehicle_id", "center_x_m", "center_y_m", "width_m", "length_m")
    if _values(left_packets["passing_vehicle"], path_fields) != _values(
            right_packets["passing_vehicle"], path_fields):
        raise ValueError("comparison passing vehicle path differs")
    left_door = _values(left_packets["door"], ("open", "side"))
    right_door = _values(right_packets["door"], ("open", "side"))
    left_activity = _values(left_packets["activity"], ("active", "kind"))
    right_activity = _values(right_packets["activity"], ("active", "kind"))
    if comparison_id in ("cargo_activity_gap", "passenger_activity_gap"):
        if left_door != right_door or left_result["activity_kind"] != right_result["activity_kind"]:
            raise ValueError("comparison fixed door or load kind differs")
        if not right_result["inactive_open_duration_s"] > left_result["inactive_open_duration_s"]:
            raise ValueError("comparison inactive-open difference absent")
    elif comparison_id == "door_side":
        if ([row["open"] for row in left_door] != [row["open"] for row in right_door]
                or left_activity != right_activity):
            raise ValueError("comparison fixed activity or door timing differs")
        if not left_result["door_closest_to_passing_traffic"] or right_result[
                "door_closest_to_passing_traffic"]:
            raise ValueError("comparison door-side difference absent")
    elif comparison_id == "load_kind":
        if left_door != right_door or [row["active"] for row in left_activity] != [
                row["active"] for row in right_activity]:
            raise ValueError("comparison fixed door or activity timing differs")
        if (left_result["activity_kind"], right_result["activity_kind"]) != (
                "cargo", "passenger"):
            raise ValueError("comparison load-kind difference absent")
    else:
        raise ValueError("unsupported exact comparison")
    return {"format": "c135087-source-bound-comparison-v1",
            "comparison_id": comparison_id, "case_ids": [a, b],
            "left_source_sha256": left_result["source_sha256"],
            "right_source_sha256": right_result["source_sha256"],
            "fixed_original_sources_reopened": True,
            "deliberate_differences_measured": True,
            "legal_necessity_or_immediacy": "unresolved"}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected_id = "testing__C135087__NRS-484B-153-3__motor_vehicle_driver__" + args.comparison
    if args.comparison_id != expected_id:
        raise ValueError("exact comparison audit identity differs")
    if args.output.exists():
        raise ValueError("refusing to overwrite comparison audit")
    result = audit_pair(args.left, args.right, args.comparison, args.plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

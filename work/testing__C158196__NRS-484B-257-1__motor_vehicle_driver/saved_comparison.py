"""Independent, source-bound audits for the two yield-branch comparisons.

This checks observed histories and source bytes. It makes no legal finding about
an immediate hazard or right of way.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


_module_path = Path(__file__).with_name("nearest_view.py")
_spec = importlib.util.spec_from_file_location("c158196_nearest_view_audit", _module_path)
nearest_view = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nearest_view)


def _read(attempt: Path, case_suffix: str) -> tuple[dict, dict]:
    packet_path = attempt / "native" / "nearest_view_packet.json"
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("case_id") != (
        "testing__C158196__NRS-484B-257-1__motor_vehicle_driver__" + case_suffix
    ):
        raise ValueError("saved case identity differs")
    nearest_view.verify_source_bytes(packet, attempt)
    return packet, nearest_view.measure(packet)


def audit(left_attempt: Path, right_attempt: Path, comparison_id: str) -> dict:
    if comparison_id == "nearest_view_conflict_response":
        left_suffix, right_suffix = "nearest_view_hold", "nearest_view_continue"
        differing = {"engineering_policy"}
    elif comparison_id == "nearest_view_traffic_occupancy":
        left_suffix, right_suffix = "nearest_view_continue", "nearest_view_clear"
        differing = {"through_vehicle_initial_station_m"}
    else:
        raise ValueError("unsupported comparison")
    left, lm = _read(left_attempt, left_suffix)
    right, rm = _read(right_attempt, right_suffix)
    for key in set(left["context"]) | set(right["context"]):
        if key not in differing and left["context"].get(key) != right["context"].get(key):
            raise ValueError(f"unreviewed fixed-condition change: {key}")
    if comparison_id == "nearest_view_conflict_response":
        if left["context"].get("engineering_policy") != "hold_for_observed_traffic":
            raise ValueError("hold policy not source-confirmed")
        if right["context"].get("engineering_policy") != "continue_through_observed_traffic":
            raise ValueError("continue policy not source-confirmed")
        if not (lm["through_occupied_during_crossing"] and rm["through_occupied_during_crossing"]):
            raise ValueError("occupied crossing not observed in both cases")
        if lm["minimum_approach_speed_mps"] >= rm["minimum_approach_speed_mps"]:
            raise ValueError("observed hold response does not differ as planned")
    else:
        if left["context"].get("engineering_policy") != "continue_through_observed_traffic" or right["context"].get("engineering_policy") != "continue_through_observed_traffic":
            raise ValueError("ego continuation policy changed")
        if not lm["through_occupied_during_crossing"] or rm["through_occupied_during_crossing"]:
            raise ValueError("observed crossing occupancy does not differ as planned")
    return {"comparison_id": comparison_id, "left": lm, "right": rm,
            "status": "source_bound_measured_not_legal_verdict"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_id")
    parser.add_argument("left_attempt", type=Path)
    parser.add_argument("right_attempt", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(audit(args.left_attempt, args.right_attempt,
                                            args.comparison_id), indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")

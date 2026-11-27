"""Source-gated measurements for the C111331 steady-red assignment.

All coordinates are original Native road coordinates in metres. The authored
plan is deliberately separate from observations; no requested signal phase or
controller target is accepted as an observed legal fact.
"""
from __future__ import annotations

import json
import math
from pathlib import Path


REQUIRED = (
    "frame", "time_s", "source_kind", "signal_state", "governing_signal_id",
    "ego_front_y_m", "ego_speed_mps", "nearest_crosswalk_y_m",
    "indicated_sign_y_m", "indicated_marking_y_m", "intersection_entry_y_m",
    "ego_lane_side", "ego_lane_extreme", "ego_maneuver", "approach_one_way",
    "downstream_direction", "pedestrian_priority_present",
    "traffic_priority_present", "pedestrian_yielded", "traffic_yielded",
)


def stop_reference(row: dict) -> tuple[str, float]:
    """Choose only a source-observed reference applicable to the scene.

    The statute has no general rule preferring a sign over a pavement marking
    when both are present with conflicting positions, so reject that geometry.
    """
    crosswalk = row["nearest_crosswalk_y_m"]
    sign = row["indicated_sign_y_m"]
    marking = row["indicated_marking_y_m"]
    if sign is not None and marking is not None and abs(sign - marking) > 0.05:
        raise ValueError("Conflicting sign and pavement marking positions")
    if crosswalk is not None:
        if sign is None and marking is None:
            raise ValueError("Crosswalk stop indication is not sourced")
        return "nearest_crosswalk", float(crosswalk)
    if sign is not None:
        return "indicated_sign", float(sign)
    if marking is not None:
        return "indicated_marking", float(marking)
    return "intersection_entry", float(row["intersection_entry_y_m"])


def analyze(rows: list[dict], *, expected_signal_id: str) -> dict:
    """Measure the original stop, hold, entry and turn/yield facts.

    Engineering sample brackets and the 0.05 m geometry tolerance describe
    measurement resolution. They are not Nevada legal thresholds.
    """
    if len(rows) < 3:
        raise ValueError("Missing original Native observation sequence")
    previous = None
    for row in rows:
        missing = set(REQUIRED) - set(row)
        if missing:
            raise ValueError("Missing original Native source: " + ", ".join(sorted(missing)))
        if row["source_kind"] != "native_observed":
            raise ValueError("Requested or synthetic source is not Native observation")
        if row["governing_signal_id"] != expected_signal_id:
            raise ValueError("Signal does not govern the observed approach")
        if row["signal_state"] not in {"red", "green"}:
            raise ValueError("Unobserved or unsupported signal state")
        for key in ("time_s", "ego_front_y_m", "ego_speed_mps", "intersection_entry_y_m"):
            if not isinstance(row[key], (int, float)) or not math.isfinite(row[key]):
                raise ValueError("Nonfinite Native measurement: " + key)
        if row["ego_speed_mps"] < 0:
            raise ValueError("Negative observed speed")
        if previous is not None and (row["frame"] != previous["frame"] + 1 or row["time_s"] <= previous["time_s"]):
            raise ValueError("Original Native frame/time join is discontinuous")
        previous = row
    reference = stop_reference(rows[0])
    if any(stop_reference(row) != reference for row in rows):
        raise ValueError("Stop reference changed inside one capture")
    if rows[0]["signal_state"] != "red":
        raise ValueError("Steady red activation was not observed")
    red = [r for r in rows if r["signal_state"] == "red"]
    green = [r for r in rows if r["signal_state"] == "green"]
    if green and any(r["frame"] < red[-1]["frame"] for r in green):
        raise ValueError("Signal phase sequence is not red then green")
    # The first frame at or beyond the reference bounds the crossing event.
    crossed = next((r for r in rows if r["ego_front_y_m"] >= reference[1]), None)
    entered = next((r for r in rows if r["ego_front_y_m"] >= r["intersection_entry_y_m"]), None)
    stopped_before = [r for r in rows if r["ego_front_y_m"] < reference[1] and r["ego_speed_mps"] == 0]
    first_stop = stopped_before[0] if stopped_before else None
    first_green = green[0] if green else None
    released_red = next((r for r in rows if first_stop is not None and r["frame"] > first_stop["frame"] and r["signal_state"] == "red" and r["ego_speed_mps"] > 0), None)
    turn = rows[0]["ego_maneuver"]
    if turn not in {"straight", "right", "left"}:
        raise ValueError("Unknown observed maneuver")
    permission_context = None
    if turn == "right":
        permission_context = bool(rows[0]["ego_lane_side"] == "right" and rows[0]["ego_lane_extreme"] and rows[0]["downstream_direction"] in {"two_directional", "one_way_right"})
    elif turn == "left":
        permission_context = bool(rows[0]["approach_one_way"] and rows[0]["ego_lane_side"] == "left" and rows[0]["ego_lane_extreme"] and rows[0]["downstream_direction"] == "one_way_left")
    yield_observation = {
        "pedestrian_priority_present": any(r["pedestrian_priority_present"] for r in rows),
        "traffic_priority_present": any(r["traffic_priority_present"] for r in rows),
        "pedestrian_yielded": all(r["pedestrian_yielded"] for r in rows if r["pedestrian_priority_present"]),
        "traffic_yielded": all(r["traffic_yielded"] for r in rows if r["traffic_priority_present"]),
    }
    return {
        "stop_reference_kind": reference[0], "stop_reference_y_m": reference[1],
        "first_full_stop_frame": first_stop["frame"] if first_stop else None,
        "first_reference_crossing_frame": crossed["frame"] if crossed else None,
        "first_intersection_entry_frame": entered["frame"] if entered else None,
        "first_green_frame": first_green["frame"] if first_green else None,
        "red_departure_frame": released_red["frame"] if released_red else None,
        "signal_governing_id": expected_signal_id,
        "observed_maneuver": turn,
        "turn_permission_context": permission_context,
        "yield_observation": yield_observation,
        "source_kind": "native_observed",
        "legal_outcome": None,
        "physical_visibility_verified": False,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True)
    parser.add_argument("--signal-id", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in Path(args.samples).read_text().splitlines() if line.strip()]
    result = analyze(rows, expected_signal_id=args.signal_id)
    Path(args.output).write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()

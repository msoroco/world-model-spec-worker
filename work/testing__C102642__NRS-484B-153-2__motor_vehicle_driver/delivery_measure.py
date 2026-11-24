"""Saved-only measurements and independent comparison checks for NRS 484B.153(2).

These functions consume sealed original-frame traces. They describe observed
acts and physical clearances; they never decide legal interference.
"""
from __future__ import annotations

import hashlib
import json
import argparse
from math import hypot, isfinite
from pathlib import Path


ACTS = {"open", "board", "alight"}
SIDES = {"left", "right"}
RATE_HZ = 20


def _point(value):
    if not isinstance(value, list) or len(value) != 2 or not all(
            isinstance(v, (float, int)) and isfinite(v) for v in value):
        raise ValueError("original XY point is missing or invalid")
    return float(value[0]), float(value[1])


def _segment_distance(a, b, c, d):
    def cross(u, v):
        return u[0] * v[1] - u[1] * v[0]

    ab = (b[0] - a[0], b[1] - a[1])
    cd = (d[0] - c[0], d[1] - c[1])
    ca = (c[0] - a[0], c[1] - a[1])
    denominator = cross(ab, cd)
    if abs(denominator) > 1e-12:
        t, u = cross(ca, cd) / denominator, cross(ca, ab) / denominator
        if 0 <= t <= 1 and 0 <= u <= 1:
            return 0.0

    def endpoint(p, x, y):
        edge = (y[0] - x[0], y[1] - x[1])
        length2 = edge[0] ** 2 + edge[1] ** 2
        t = 0 if length2 == 0 else max(0, min(1, ((p[0] - x[0]) * edge[0] +
                                                  (p[1] - x[1]) * edge[1]) / length2))
        return hypot(p[0] - x[0] - t * edge[0],
                     p[1] - x[1] - t * edge[1])

    return min(endpoint(a, c, d), endpoint(b, c, d),
               endpoint(c, a, b), endpoint(d, a, b))


def read_sealed_trace(path: Path, expected_sha256: str) -> dict:
    """Bind the measurement to the supplied original source bytes."""
    data = Path(path).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("original trace hash mismatch")
    trace = json.loads(data)
    if not isinstance(trace, dict) or trace.get("source_kind") != "native_original":
        raise ValueError("trace is not declared original Native acquisition")
    return trace


def measure(trace: dict, *, expected_case_id: str, expected_act: str,
            expected_side: str) -> dict:
    if expected_act not in ACTS or expected_side not in SIDES:
        raise ValueError("unknown selected act or door side")
    if trace.get("case_id") != expected_case_id or trace.get("source_kind") != "native_original":
        raise ValueError("wrong case or unbound source")
    if trace.get("sample_rate_hz") != RATE_HZ:
        raise ValueError("original trace must use the 20 Hz capture clock")
    frames = trace.get("frames")
    if not isinstance(frames, list) or len(frames) < 3:
        raise ValueError("missing original frames")
    ids = [frame.get("frame_id") for frame in frames]
    if any(type(value) is not int for value in ids) or any(
            b != a + 1 for a, b in zip(ids, ids[1:])):
        raise ValueError("original frame identities are noncontiguous")
    times = [frame.get("sim_time_s") for frame in frames]
    if any(not isinstance(value, (int, float)) or not isfinite(value) for value in times) or any(
            abs((b - a) - 1 / RATE_HZ) > 1e-4 for a, b in zip(times, times[1:])):
        raise ValueError("original timestamps do not follow the 20 Hz clock")
    context = trace.get("fixed_context")
    if not isinstance(context, dict) or not all(context.get(k) for k in (
            "map_sha256", "survey_sha256", "loading_site_id", "parked_vehicle_id",
            "driver_id", "passing_vehicle_id", "traffic_route_id", "camera_contract_id")):
        raise ValueError("fixed scene context is missing")
    parked = _point(trace.get("parked_center_xy"))
    heading = _point(trace.get("parked_heading_xy"))
    heading_length = hypot(*heading)
    if heading_length <= 0:
        raise ValueError("parked vehicle heading is invalid")
    heading = heading[0] / heading_length, heading[1] / heading_length
    sides, act_frames, moving_frames, clearances, responses = set(), [], [], [], []
    passing_history = []
    for frame in frames:
        if set(frame.get("camera_frames", {})) != {"front", "rear", "left", "right"}:
            raise ValueError("four original camera frame identities are required")
        if any(frame["camera_frames"][view] != frame["frame_id"] for view in (
                "front", "rear", "left", "right")):
            raise ValueError("camera frame identity mismatch")
        if frame.get("selected_driver_id") != context["driver_id"]:
            raise ValueError("selected driver was not bound to the observed act")
        act = frame.get("observed_act")
        if act not in ACTS | {"none"}:
            raise ValueError("observed act is absent or unknown")
        if act != "none":
            if act != expected_act or frame.get("act_side") != expected_side:
                raise ValueError("observed act or side differs from selected case")
            act_frames.append(frame["frame_id"])
        center = _point(frame.get("passing_center_xy"))
        relative = (center[0] - parked[0], center[1] - parked[1])
        signed = heading[0] * relative[1] - heading[1] * relative[0]
        if abs(signed) < 0.05:
            raise ValueError("passing path is ambiguous at parked centerline")
        sides.add("left" if signed > 0 else "right")
        speed = frame.get("passing_speed_mps")
        if not isinstance(speed, (int, float)) or not isfinite(speed) or speed < 0:
            raise ValueError("original moving-vehicle speed is absent")
        if speed > 0.1:
            moving_frames.append(frame["frame_id"])
        passing_body = frame.get("passing_body_xy")
        if not isinstance(passing_body, list) or len(passing_body) < 2:
            raise ValueError("original passing body vertices are required in every frame")
        passing_history.append({"frame_id": frame["frame_id"],
                                "center_xy": list(center), "speed_mps": float(speed),
                                "body_xy": [list(_point(v)) for v in passing_body]})
        if act != "none" and speed > 0.1:
            envelope = frame.get("act_envelope_xy")
            vehicle = frame.get("passing_body_xy")
            if not isinstance(envelope, list) or not isinstance(vehicle, list) or (
                    len(envelope) < 2 or len(vehicle) < 2):
                raise ValueError("original act and passing body vertices are required")
            act_points = [_point(v) for v in envelope]
            vehicle_points = [_point(v) for v in vehicle]
            minimum = min(_segment_distance(act_points[i], act_points[i + 1],
                                            vehicle_points[j], vehicle_points[j + 1])
                          for i in range(len(act_points) - 1)
                          for j in range(len(vehicle_points) - 1))
            clearances.append({"frame_id": frame["frame_id"], "body_gap_m": minimum})
            response = frame.get("passing_response")
            if not isinstance(response, dict) or not all(isinstance(response.get(k), (int, float))
                                                          for k in ("brake", "acceleration_mps2")):
                raise ValueError("original traffic response is absent")
            responses.append({"frame_id": frame["frame_id"], **response})
    if len(sides) != 1 or not act_frames or not set(act_frames) & set(moving_frames):
        raise ValueError("act and moving traffic did not overlap on one passing side")
    if not clearances:
        raise ValueError("no measured interaction frames")
    return {"case_id": expected_case_id, "observed_act": expected_act,
            "act_side": expected_side, "passing_side": next(iter(sides)),
            "act_on_closest_side": expected_side == next(iter(sides)),
            "act_frame_ids": act_frames, "moving_frame_ids": moving_frames,
            "body_gap_by_frame_m": clearances,
            "minimum_body_gap_m": min(row["body_gap_m"] for row in clearances),
            "passing_response": responses,
            "passing_history": passing_history,
            "fixed_context": context,
            "legal_interference": "unresolved_judgment"}


def audit_pair(left: dict, right: dict, *, deliberate_difference: str) -> dict:
    """Reject a comparison whose fixed sources or named variation drifted."""
    if left["case_id"] == right["case_id"]:
        raise ValueError("comparison needs distinct cases")
    if left["legal_interference"] != "unresolved_judgment" or (
            right["legal_interference"] != "unresolved_judgment"):
        raise ValueError("measurement must not provide a legal verdict")
    if left["fixed_context"] != right["fixed_context"]:
        raise ValueError("fixed scene context changed")
    if deliberate_difference == "body_gap_m":
        if (left["observed_act"], left["act_side"]) != (
                right["observed_act"], right["act_side"]):
            raise ValueError("act or side changed during clearance comparison")
        if left["minimum_body_gap_m"] == right["minimum_body_gap_m"]:
            raise ValueError("clearance comparison has no measured difference")
        if left["act_frame_ids"] != right["act_frame_ids"]:
            raise ValueError("act timing changed during clearance comparison")
        if [(row["frame_id"], row["speed_mps"]) for row in left["passing_history"]] != [
                (row["frame_id"], row["speed_mps"]) for row in right["passing_history"]]:
            raise ValueError("passing speed history changed during clearance comparison")
    elif deliberate_difference == "act_side":
        if left["observed_act"] != right["observed_act"] or (
                left["act_side"] == right["act_side"]):
            raise ValueError("side comparison changed act or omitted side change")
        if left["passing_history"] != right["passing_history"]:
            raise ValueError("passing trajectory changed during side comparison")
    elif deliberate_difference == "observed_act":
        if left["act_side"] != right["act_side"] or (
                left["observed_act"] == right["observed_act"]):
            raise ValueError("act comparison changed side or omitted act change")
        if left["passing_history"] != right["passing_history"]:
            raise ValueError("passing trajectory changed during act comparison")
    else:
        raise ValueError("undeclared comparison variable")
    return {"case_ids": [left["case_id"], right["case_id"]],
            "deliberate_difference": deliberate_difference,
            "fixed_context_checked": True,
            "legal_interference": "unresolved_judgment"}


def audit_source_pair(left_source: Path, left_sha256: str, left_case_id: str,
                      left_act: str, left_side: str, right_source: Path,
                      right_sha256: str, right_case_id: str, right_act: str,
                      right_side: str, deliberate_difference: str) -> dict:
    """Independently remeasure both sealed sources before comparing them."""
    left = measure(read_sealed_trace(left_source, left_sha256),
                   expected_case_id=left_case_id, expected_act=left_act,
                   expected_side=left_side)
    right = measure(read_sealed_trace(right_source, right_sha256),
                    expected_case_id=right_case_id, expected_act=right_act,
                    expected_side=right_side)
    result = audit_pair(left, right, deliberate_difference=deliberate_difference)
    result["source_sha256"] = [left_sha256, right_sha256]
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--act", choices=sorted(ACTS), required=True)
    parser.add_argument("--side", choices=sorted(SIDES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = measure(read_sealed_trace(args.source, args.source_sha256),
                     expected_case_id=args.case_id, expected_act=args.act,
                     expected_side=args.side)
    result["original_source_sha256"] = args.source_sha256
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")


if __name__ == "__main__":
    main()

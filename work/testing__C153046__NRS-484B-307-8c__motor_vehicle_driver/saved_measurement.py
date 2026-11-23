"""Measure original red-left attempt geometry without assigning a legal verdict.

This saved pass rejects a changed site or broken frame join. Metrics from a CPU
fixture exercise the algorithm but never count as physical delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_case_plan import AID, KINDS
from source_bound_scene import build as bind_scene


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("nonfinite original measurement")
    return float(value)


def xy(value, name: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) < 2:
        raise ValueError("missing original XY: " + name)
    return finite(value[0]), finite(value[1])


def _progress(point, reference, direction):
    return sum((point[i] - reference[i]) * direction[i] for i in (0, 1))


def _lateral(point, reference, direction):
    return direction[0] * (point[1] - reference[1]) - direction[1] * (point[0] - reference[0])


def measure(packet_path: Path, trace_path: Path, case_id: str) -> dict:
    if not case_id.startswith(AID + "__"):
        raise ValueError("wrong assignment case identity")
    suffix = case_id[len(AID) + 2:]
    if suffix not in KINDS:
        raise ValueError("unknown exact case")
    scene = bind_scene(packet_path, suffix)
    trace_path = Path(trace_path)
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("original trace needs multiple frames")
    packet = json.loads(Path(packet_path).read_text())
    signal_id = str(packet["signal"]["native_actor_id"])
    direction = scene["approach_direction_xy"]
    reference = scene["approach_reference_xy"]
    stop = scene["stop_boundary_progress_m"]
    previous_frame = previous_time = None
    extracted = []
    for row in rows:
        frame = row.get("native_frame")
        if (row.get("case_id") != case_id or
                row.get("source_packet_sha256") != scene["source_packet_sha256"] or
                row.get("selected_approach_lane_id") != scene["selected_approach_lane_id"] or
                row.get("original_sample_claim") is not True or
                not isinstance(frame, dict) or frame.get("origin") != "native_world_snapshot"):
            raise ValueError("trace lacks exact original case/source join")
        number = frame.get("frame")
        if type(number) is not int or (previous_frame is not None and number != previous_frame + 1):
            raise ValueError("original frame sequence missing or reordered")
        time_s = finite(frame.get("time_s"))
        if ((previous_time is not None and time_s <= previous_time) or
                abs(time_s - finite(row.get("time_s"))) > 1e-6):
            raise ValueError("original frame time join differs")
        if str(frame.get("signal_actor_id")) != signal_id:
            raise ValueError("original signal actor differs from site")
        observed_red = str(frame.get("signal_state")).rsplit(".", 1)[-1].lower() == "red"
        if (row.get("signal") == "steady_red_alone") != observed_red:
            raise ValueError("original signal state differs from controller observation")
        ego = frame.get("ego")
        if not isinstance(ego, dict):
            raise ValueError("original ego state missing")
        center = xy(ego.get("location_xyz_m"), "ego center")
        velocity = ego.get("velocity_xyz_mps")
        if not isinstance(velocity, list) or len(velocity) < 2:
            raise ValueError("original ego velocity missing")
        speed = math.hypot(finite(velocity[0]), finite(velocity[1]))
        vertices = ego.get("body_vertices_xyz_m")
        if not isinstance(vertices, list) or len(vertices) < 4:
            raise ValueError("original full ego body missing")
        front = max(_progress(xy(vertex, "ego body"), reference, direction) for vertex in vertices)
        for key, actors in (("pedestrian_conflict", frame.get("pedestrians")),
                            ("traffic_conflict", frame.get("other_traffic"))):
            if type(row.get(key)) is not bool:
                raise ValueError("original conflict observation must be boolean: " + key)
            if not isinstance(actors, list) or (row.get(key) is True and not actors):
                raise ValueError("declared conflict lacks original participant: " + key)
            for actor in actors:
                if not isinstance(actor, dict) or len(actor.get("body_vertices_xyz_m", [])) < 4:
                    raise ValueError("original participant full body missing")
        extracted.append({"frame": number, "time_s": time_s, "center": center,
                          "speed_m_s": speed, "front_progress_m": front,
                          "boundary_crossed": front > stop,
                          "red": observed_red,
                          "pedestrian_conflict": row["pedestrian_conflict"],
                          "traffic_conflict": row["traffic_conflict"]})
        previous_frame, previous_time = number, time_s
    first_cross = next((index for index, item in enumerate(extracted)
                        if item["boundary_crossed"]), None)
    before = extracted if first_cross is None else extracted[:first_cross]
    stopped = [item for item in before if item["speed_m_s"] <= 0.05 and
               item["front_progress_m"] <= stop]
    stop_duration = 0.0
    if stopped:
        chain = [stopped[0]]
        for item in stopped[1:]:
            if item["frame"] == chain[-1]["frame"] + 1:
                chain.append(item)
            else:
                stop_duration = max(stop_duration, chain[-1]["time_s"] - chain[0]["time_s"])
                chain = [item]
        stop_duration = max(stop_duration, chain[-1]["time_s"] - chain[0]["time_s"])
    first_center = extracted[0]["center"]
    first_lateral = _lateral(first_center, reference, direction)
    lane_centers = scene["approach_lane_centers_xy"]
    nearest_lane = min(lane_centers,
                       key=lambda name: abs(first_lateral - _lateral(lane_centers[name], reference, direction)))
    last_center = extracted[-1]["center"]
    displacement = (last_center[0] - first_center[0], last_center[1] - first_center[1])
    left_displacement_m2 = direction[0] * displacement[1] - direction[1] * displacement[0]
    crossing_conflicts = None if first_cross is None else {
        "pedestrian": extracted[first_cross]["pedestrian_conflict"],
        "other_traffic": extracted[first_cross]["traffic_conflict"]}
    return {"format": "c153046-source-bound-measurement-draft", "case_id": case_id,
            "site_packet_sha256": scene["source_packet_sha256"],
            "source_hashes": scene["source_hashes"],
            "receiving_direction_request": scene["receiving_direction_request"],
            "signal_actor_id": signal_id,
            "trace_sha256": sha(trace_path), "frames": len(extracted),
            "first_frame": extracted[0]["frame"], "last_frame": extracted[-1]["frame"],
            "first_boundary_crossing_frame": None if first_cross is None else extracted[first_cross]["frame"],
            "stationary_duration_before_boundary_s": stop_duration,
            "engineering_stop_observed": stop_duration >= 0.5,
            "first_approach_lane_id": nearest_lane,
            "selected_approach_lane_id": scene["selected_approach_lane_id"],
            "left_displacement_cross_m2": left_displacement_m2,
            "conflicts_at_first_boundary_crossing": crossing_conflicts,
            "signal_red_frames": sum(item["red"] for item in extracted),
            "measurement_status": "objective_trace_metrics_only",
            "conflict_geometry_verified": False, "physical_acceptance_claimed": False,
            "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain previous saved measurement")
    result = measure(Path(args.packet), Path(args.trace), args.case)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["case_id"], result["frames"], result["measurement_status"])


if __name__ == "__main__":
    main()

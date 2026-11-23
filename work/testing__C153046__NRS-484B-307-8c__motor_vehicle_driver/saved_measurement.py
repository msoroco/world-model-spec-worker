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
from recording_description import build as recording_description
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


def finalize_attempt(attempt: Path, output: Path) -> dict:
    """Build saved-only channels and a canonical-shaped Native result from original files."""
    attempt = Path(attempt).resolve()
    output = Path(output).resolve()
    if output != attempt / "analysis-report.json":
        raise ValueError("analysis report must stay in the selected attempt")
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("retain previous saved analysis")
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id")
    if (config.get("law_id") != "NRS-484B-307-8c" or
            config.get("cell_id") != "C153046" or
            config.get("case", {}).get("case_id") != case_id):
        raise ValueError("saved analysis exact case binding differs")
    site = attempt / "site.json"
    trace = attempt / "trace.jsonl"
    if not site.is_file() or not trace.is_file():
        raise ValueError("Missing required source: site.json or trace.jsonl")
    result = measure(site, trace, case_id)
    rows = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    mapping_path = attempt / "video_frames.jsonl"
    if not mapping_path.is_file():
        raise ValueError("Missing required source: video_frames.jsonl")
    mapping = [json.loads(line) for line in mapping_path.read_text().splitlines() if line.strip()]
    if len(mapping) != len(rows) or any(
            item.get("video_frame") != index or item.get("carla_frame") != row["frame"] or
            abs(finite(item.get("time_s")) - finite(row["time_s"])) > 1e-6
            for index, (item, row) in enumerate(zip(mapping, rows))):
        raise ValueError("original video and trace frame map differs")
    video_names = ["overview.mkv", "approach.mkv", "reference_corner.mkv",
                   "driver_reference.mkv"]
    if any(not (attempt / name).is_file() or (attempt / name).stat().st_size == 0
           for name in video_names):
        raise ValueError("Missing required source: original four-view media")
    channel_plan = recording_description()
    signals = [row["native_frame"]["signal_state"] for row in rows]
    values = {
        "official steady red alone": [state.rsplit(".", 1)[-1].lower() == "red" for state in signals],
        "antecedent stop location": [row["distance_to_stop_boundary_m"] for row in rows],
        "complete stop": [{"speed_mps": row["speed_mps"],
                           "distance_to_stop_boundary_m": row["distance_to_stop_boundary_m"]}
                          for row in rows],
        "extreme left of one-way approach": [row["selected_approach_lane_id"] for row in rows],
        "receiving one-way to left": [result["receiving_direction_request"] for _ in rows],
        "pedestrian right-of-way": [{"actors": row["native_frame"]["pedestrians"],
                                      "conflict_observed": row["pedestrian_conflict"]} for row in rows],
        "other traffic right-of-way": [{"actors": row["native_frame"]["other_traffic"],
                                         "conflict_observed": row["traffic_conflict"]} for row in rows],
        "yield response": [{"control_request": row["control_request"],
                            "phase": row["requested_phase"],
                            "pedestrian_conflict": row["pedestrian_conflict"],
                            "traffic_conflict": row["traffic_conflict"]} for row in rows],
    }
    expected = {item["name"] for item in channel_plan["channels"]}
    if set(values) != expected:
        raise ValueError("saved channel plan differs from source observations")
    packet = json.loads(site.read_text())
    contexts = {
        "reviewed_one_way_left_turn_site": {
            "site_packet_sha256": sha(site), "source_hashes": result["source_hashes"],
            "approach": packet["approach"], "receiving": packet["receiving"]},
        "reviewed_signal_and_stop_hierarchy": {
            "site_packet_sha256": sha(site), "signal": packet["signal"],
            "stop_boundary": packet["stop_boundary"]},
    }
    evidence = []
    prepared = {}
    for index, channel in enumerate(channel_plan["channels"]):
        name = channel["name"]
        reference = f"channels/stream-{index:02d}.jsonl"
        prepared[reference] = "".join(json.dumps({"time_s": row["time_s"],
                                                   "value": value}, sort_keys=True) + "\n"
                                       for row, value in zip(rows, values[name]))
        evidence.append({"name": name, "unit": channel["unit"], "reference": reference})
    for index, context in enumerate(channel_plan["context_inputs"]):
        name = context["name"]
        reference = f"channels/context-{index:02d}.json"
        prepared[reference] = json.dumps({name: contexts[name]}, sort_keys=True) + "\n"
        evidence.append({"name": name, "unit": context["unit"], "reference": reference})
    stop_observed = result["stationary_duration_before_boundary_s"]
    target = {"target": "engineering stationary interval before boundary",
              "requested": 0.5, "measured": stop_observed,
              "method": "measure original Native full-body and velocity frames",
              "tolerance": 0.0, "matched": stop_observed >= 0.5,
              "physical_cause_confirmed": False,
              "cause_evidence": ["trace.jsonl", "site.json"]}
    # A lower-bound comparison is categorical; avoid a false numeric equality check.
    target["requested"] = "at least 0.5 s (engineering request, not legal threshold)"
    complete = bool(rows[-1].get("junction_exited"))
    native_result = {
        "case_id": case_id, "measured_values": result,
        "target_checks": [target], "setup_confirmed": False,
        "behavior_attempted": all(isinstance(row.get("control_request"), dict) for row in rows),
        "maneuver_completed": complete,
        "termination_reason": "planned 600-frame window" if len(rows) == 600 else "incomplete original frame window",
        "physical_failure_flags": [] if complete else ["receiving-road exit unobserved"],
        "trace_reference": "trace.jsonl", "video_references": video_names,
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": channel_plan, "recording_evidence": evidence,
        "realized_observables": {}, "physical_acceptance_claimed": False}
    hashes = {name: sha(attempt / name) for name in ("site.json", "trace.jsonl",
                                                       "video_frames.jsonl", *video_names)}
    measured = {}
    for key in ("stationary_duration_before_boundary_s", "engineering_stop_observed",
                "first_approach_lane_id", "selected_approach_lane_id",
                "left_displacement_cross_m2", "signal_red_frames",
                "first_boundary_crossing_frame", "conflicts_at_first_boundary_crossing"):
        value = result[key]
        if value is not None:
            measured[key] = {"method": "measure", "value": value,
                             "sources": {name: hashes[name] for name in ("site.json", "trace.jsonl")}}
    measured["red_left_turn_observation"] = {
        "method": "measure",
        "value": {
            "case_id": case_id,
            "site_packet_sha256": result["site_packet_sha256"],
            "signal_actor_id": result["signal_actor_id"],
            "signal_red_frames": result["signal_red_frames"],
            "stationary_duration_before_boundary_s": result["stationary_duration_before_boundary_s"],
            "engineering_stop_observed": result["engineering_stop_observed"],
            "first_approach_lane_id": result["first_approach_lane_id"],
            "selected_approach_lane_id": result["selected_approach_lane_id"],
            "receiving_direction_request": result["receiving_direction_request"],
            "first_boundary_crossing_frame": result["first_boundary_crossing_frame"],
            "conflicts_at_first_boundary_crossing": result["conflicts_at_first_boundary_crossing"],
            "left_displacement_cross_m2": result["left_displacement_cross_m2"],
        },
        "sources": {name: hashes[name] for name in ("site.json", "trace.jsonl")},
    }
    report = {"format": "c153046-saved-analysis-draft", "case_id": case_id,
              "measurement": result, "measurements": measured, "sources": hashes,
              "physical_acceptance_claimed": False}
    channels = attempt / "channels"
    channels.mkdir()
    for name, content in prepared.items():
        (attempt / name).write_text(content)
    (attempt / "result.json").write_text(json.dumps(native_result, indent=2, allow_nan=False) + "\n")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt")
    parser.add_argument("--packet")
    parser.add_argument("--trace")
    parser.add_argument("--case")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.attempt:
        if any((args.packet, args.trace, args.case)):
            parser.error("--attempt uses the exact materialized case and original sources")
        report = finalize_attempt(Path(args.attempt), Path(args.output))
        print(report["case_id"], report["measurement"]["frames"])
        return
    if not all((args.packet, args.trace, args.case)):
        parser.error("--packet, --trace and --case are required for direct measurement")
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain previous saved measurement")
    result = measure(Path(args.packet), Path(args.trace), args.case)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["case_id"], result["frames"], result["measurement_status"])


if __name__ == "__main__":
    main()

"""Saved-only source-bound yield-crosswalk measurement; no legal safety verdict."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from measure_yield_crosswalk import CAMERAS, FRAMES, HASHES, measure
from worker_exchange.native_output import physical_result, write_result


def source(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(root, name):
    return [json.loads(line) for line in source(root, name).read_text().splitlines() if line.strip()]


def inspect_sources(root, context):
    paths = context.get("source_files", {})
    if set(paths) != set(HASHES):
        raise ValueError("Original yield source inventory incomplete")
    for key, name in paths.items():
        if sha(source(root, name)) != context.get(key + "_sha256"):
            raise ValueError("Original yield source hash differs: " + key)
    map_hash = context["native_map_sha256"]
    for name in ("yield_sign.json", "near_crosswalk.json", "intersecting_traffic.json"):
        if json.loads(source(root, name).read_text()).get("map_readback_sha256") != map_hash:
            raise ValueError("Original map/feature readback hash differs: " + name)
    safety = json.loads(source(root, "safety_context.json").read_text())
    if safety.get("safety_stop_required") != "unassessed" or safety.get("independent_judgment_required") is not True:
        raise ValueError("Conditional safety judgment was invented or omitted")


def inspect_original_join(root, context, motion, video, trace):
    if len(motion) != FRAMES or len(video) != FRAMES or len(trace) != FRAMES:
        raise ValueError("Missing complete 600-frame saved source join")
    ego_bodies = rows(root, "ego_body.jsonl")
    other_bodies = rows(root, "intersecting_body.jsonl")
    if len(ego_bodies) != FRAMES or len(other_bodies) != FRAMES:
        raise ValueError("Original actor body history incomplete")
    for i, (state, frame, core, ego, other) in enumerate(
            zip(motion, video, trace, ego_bodies, other_bodies)):
        native = state.get("native_frame")
        if (state.get("video_frame") != i or frame.get("video_frame") != i or
                frame.get("native_frame") != native or core.get("frame") != native or
                abs(frame.get("time_s", -1) - state.get("time_s", -2)) > 1e-6 or
                abs(core.get("time_s", -3) - state.get("time_s", -4)) > 1e-6 or
                frame.get("source_cameras") != state.get("source_cameras") or
                ego.get("native_frame") != native or other.get("native_frame") != native or
                ego.get("actor_id") != state.get("ego_actor_id") or
                other.get("actor_id") != state.get("intersecting_actor_id")):
            raise ValueError("Original frame, Core or actor identity join differs")
        hashes = frame.get("camera_rgb_sha256")
        if (not isinstance(hashes, dict) or set(hashes) != CAMERAS or
                any(not isinstance(value, str) or len(value) != 64 for value in hashes.values())):
            raise ValueError("Original four camera RGB source hashes missing")
        vertices = ego.get("body_vertices_m", [])
        if len(vertices) < 4:
            raise ValueError("Original ego body vertices missing")
        minimum = min(vertex[0] for vertex in vertices)
        maximum = max(vertex[0] for vertex in vertices)
        if (abs((minimum + maximum) / 2 - state.get("ego_x_m", 999)) > .01 or
                abs(maximum - minimum - state.get("ego_length_m", -1)) > .01):
            raise ValueError("Original ego body/motion extent differs")
        if len(other.get("body_vertices_m", [])) < 4:
            raise ValueError("Original intersecting actor body vertices missing")
    for name in CAMERAS:
        count = subprocess.check_output(
            ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1",
             str(source(root, name + ".mkv"))], text=True, timeout=120).strip()
        if count != str(FRAMES):
            raise ValueError("Original source camera full decode differs: " + name)


def measure_crosswalk_position(observation):
    return {"first_stop_front_x_m": observation["first_stop_front_x_m"],
            "first_stop_before_crosswalk": observation["first_stop_before_crosswalk"],
            "first_stop_in_crosswalk": observation["first_stop_in_crosswalk"],
            "crosswalk_entry_frame": observation["first_crosswalk_entry_frame"],
            "legal_compliance": "unassessed"}


def measure_yield_governance(observation):
    return {"governing_sign": "YIELD", "near_side_crosswalk": True,
            "intersecting_vehicle_y_at_stop_m": observation["intersecting_vehicle_y_at_stop_m"],
            "safety_stop_required": "unassessed"}


def finalize(attempt, output):
    root = Path(attempt).resolve()
    destination = Path(output)
    if destination.exists():
        raise ValueError("Retain prior selected analysis output")
    config = json.loads(source(root, "config.json").read_text())
    case = config["selected_case_id"]
    context = json.loads(source(root, "yield_context.json").read_text())
    if case != context.get("case_id"):
        raise ValueError("Selected case and original context differ")
    if context.get("source_kind") not in {"original_native_yield_crosswalk_readback", "synthetic_yield_fixture"}:
        raise ValueError("Unknown yield source kind")
    inspect_sources(root, context)
    motion = rows(root, "yield_motion.jsonl")
    video = rows(root, "video_frames.jsonl")
    trace = rows(root, "trace.jsonl")
    if context["source_kind"] == "original_native_yield_crosswalk_readback":
        inspect_original_join(root, context, motion, video, trace)
    observation = measure(context, motion)
    if context["source_kind"] == "original_native_yield_crosswalk_readback":
        raw = json.loads(source(root, "acquisition-provenance.json").read_text())
        if raw.get("provenance_kind") != "native" or raw.get("diagnostic_fixture") is not False:
            raise ValueError("Original acquisition provenance missing")
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=True)
    (channel_dir / "conditional_stop_position.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {
            "front_x_m": row["ego_x_m"] + row["ego_length_m"] / 2,
            "speed_mps": row["ego_speed_mps"]}}, allow_nan=False) + "\n" for row in motion))
    (channel_dir / "ego_pose.jsonl").write_text("".join(
        json.dumps({"time_s": row["time_s"], "value": {
            "x_m": row["ego_x_m"], "y_m": -1.75, "heading_deg": 0,
            "speed_mps": row["ego_speed_mps"]}}, allow_nan=False) + "\n" for row in motion))
    context_sources = {"governing_yield_sign": "yield_sign.json",
        "near_side_crosswalk": "near_crosswalk.json",
        "intersecting_traffic": "intersecting_traffic.json",
        "safety_context": "safety_context.json"}
    for channel, filename in context_sources.items():
        (channel_dir / (channel + ".json")).write_text(json.dumps({
            channel: json.loads(source(root, filename).read_text()),
            "source_sha256": sha(source(root, filename))}, allow_nan=False) + "\n")
    result = {"case_id": case, "measured_values": observation,
        "target_checks": [{"target": "first stop before nearest-side crosswalk",
                           "requested": config["requested_stop_before_crosswalk"],
                           "measured": observation["first_stop_before_crosswalk"],
                           "method": "source-body front extent and first recorded rest versus original crosswalk edge",
                           "tolerance": "0.1 m/s recorded-rest diagnostic only; no statutory safety cutoff",
                           "matched": observation["first_stop_before_crosswalk"] == config["requested_stop_before_crosswalk"],
                           "physical_cause_confirmed": False,
                           "cause_evidence": ["yield_motion.jsonl", "ego_body.jsonl", "near_crosswalk.json"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False, "termination_reason": "600 saved frames measured; physical and legal review pending",
        "physical_failure_flags": ["original physical success not independently confirmed"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in sorted(CAMERAS)],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "conditional_stop_position", "unit": "m,m/s",
                                "reference": "channels/conditional_stop_position.jsonl"},
                               {"name": "ego_pose", "unit": "m,deg",
                                "reference": "channels/ego_pose.jsonl"}] +
                              [{"name": name, "unit": "structured",
                                "reference": "channels/" + name + ".json"}
                               for name in context_sources],
        "realized_observables": {},
        "provenance_kind": "native" if context["source_kind"] == "original_native_yield_crosswalk_readback" else "synthetic_fixture",
        "diagnostic_fixture": context["source_kind"] != "original_native_yield_crosswalk_readback",
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    result = physical_result(root, result)
    write_result(root, result)
    measurement_sources = {
        "crosswalk_stop_position": ("measure_crosswalk_position",
            measure_crosswalk_position(observation),
            ["near_crosswalk.json", "ego_body.jsonl", "yield_motion.jsonl", "video_frames.jsonl"]),
        "conditional_yield_context": ("measure_yield_governance",
            measure_yield_governance(observation),
            ["yield_sign.json", "intersecting_traffic.json", "safety_context.json", "yield_motion.jsonl"]),
    }
    measurements = {key: {"method": method, "value": value,
                          "sources": {name: sha(source(root, name)) for name in names}}
                    for key, (method, value, names) in measurement_sources.items()}
    measured = {"format": "worker-yield-crosswalk-selected-measurement",
                "case_id": case, "measurement": observation,
                "measurements": measurements,
                "source_sha256": {key: context[key + "_sha256"] for key in HASHES},
                "safety_stop_required": "unassessed", "legal_compliance": "unassessed",
                "physical_acceptance_claimed": False}
    destination.write_text(json.dumps(measured, indent=2, allow_nan=False) + "\n")
    return measured


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), allow_nan=False))

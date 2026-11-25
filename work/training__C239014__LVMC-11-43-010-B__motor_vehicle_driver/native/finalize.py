"""Saved-only original actor, map and frame joins for roundabout entry.

The six-metre conflict neighborhood is an engineering diagnostic. It is not a
statutory sufficient-gap rule, and this finalizer returns no legal verdict.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("native-raw-actors.jsonl", "control-intent.jsonl", "video_frames.jsonl",
           "trace.jsonl", "roundabout-map-readback.json", "road.xodr")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def analyze(attempt):
    attempt = Path(attempt)
    for name in (*SOURCES, "config.json", *(name + ".mkv" for name in CAMERAS)):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("case_id")
    if (config.get("selected_case_id") != case_id or
            not str(case_id).startswith("training__C239014__LVMC-11-43-010-B__motor_vehicle_driver__") or
            config.get("law_id") != "LVMC-11-43-010-B" or
            config.get("cell_id") != "C239014" or config.get("rate_hz") != 20 or
            config.get("duration_s") != 30):
        raise ValueError("Exact saved case contract differs")
    actor_rows = rows(attempt / SOURCES[0])
    controls = rows(attempt / SOURCES[1])
    frames = rows(attempt / SOURCES[2])
    trace = rows(attempt / SOURCES[3])
    if any(len(stream) != FRAMES for stream in (actor_rows, controls, frames, trace)):
        raise ValueError("Incomplete 600-frame original source join")
    map_readback = json.loads((attempt / "roundabout-map-readback.json").read_text())
    if map_readback.get("source_kind") != "native_map_readback" or {
            row.get("road_id") for row in map_readback.get("samples", [])} != {1, 2}:
        raise ValueError("Native roundabout map readback missing")
    entries = []
    waits = []
    conflict = []
    actor_ids = {}
    for i, (record, intent, frame, movement) in enumerate(zip(
            actor_rows, controls, frames, trace)):
        native = frame.get("native_frame")
        t = frame.get("time_s")
        if (frame.get("video_frame") != i or not isinstance(native, int) or
                not isinstance(t, (float, int)) or not math.isfinite(t) or
                record.get("video_frame") != i or intent.get("video_frame") != i or
                record.get("native_frame") != native or intent.get("native_frame") != native or
                movement.get("frame") != native or
                abs(record.get("time_s", -100) - t) > 1e-4 or
                abs(intent.get("time_s", -100) - t) > 1e-4 or
                abs(movement.get("time_s", -100) - t) > 1e-4 or
                (i and (native <= frames[i-1]["native_frame"] or t <= frames[i-1]["time_s"]))):
            raise ValueError("Original frame/time identity differs")
        if set(frame.get("camera_native_frames", {})) != set(CAMERAS) or any(
                value != native for value in frame["camera_native_frames"].values()):
            raise ValueError("Four-camera original frame join differs")
        if record.get("case_id") != case_id:
            raise ValueError("Original actor case identity differs")
        actors = record.get("actors", [])
        by_role = {actor.get("role"): actor for actor in actors}
        if set(by_role) != {"ego", "lead", "follower"} or len(actors) != 3:
            raise ValueError("Required circulating actor source missing")
        for role, actor in by_role.items():
            if actor.get("actor_id") is None or actor.get("blueprint_id") is None:
                raise ValueError("Original actor identity missing")
            if role in actor_ids and actor_ids[role] != actor["actor_id"]:
                raise ValueError("Original actor identity changed")
            actor_ids[role] = actor["actor_id"]
            if any(not isinstance(actor.get(key), (float, int)) or not math.isfinite(actor[key])
                   for key in ("x_m", "y_m", "speed_mps", "bbox_half_length_m",
                               "bbox_half_width_m")):
                raise ValueError("Original actor motion absent or nonfinite")
        ego = by_role["ego"]
        if ego.get("road_id") == 1:
            entries.append(i)
        elif ego.get("road_id") == 2 and ego["speed_mps"] <= .2:
            waits.append(i)
        if any(actor.get("road_id") != 1 for actor in
               (by_role["lead"], by_role["follower"])):
            raise ValueError("Circulating actor left the recorded ring")
        if any(math.dist((actor["x_m"], actor["y_m"]), (0, -20)) <= 6
               for actor in (by_role["lead"], by_role["follower"])):
            conflict.append(i)
    if not entries:
        raise ValueError("Original ego ring entry absent")
    entry = entries[0]
    if not waits or max(waits) >= entry:
        raise ValueError("Original pre-entry wait absent")
    before = max((i for i in conflict if i <= entry), default=None)
    after = min((i for i in conflict if i > entry), default=None)
    if before is None or after is None:
        raise ValueError("Original traffic gap lacks both source brackets")
    return {"format": "c239014-roundabout-saved-meter-v1", "case_id": case_id,
            "source_sha256": {name: sha(attempt / name) for name in SOURCES},
            "video_sha256": {name + ".mkv": sha(attempt / (name + ".mkv")) for name in CAMERAS},
            "actor_ids": actor_ids, "frames": FRAMES,
            "first_entry_frame": entry, "wait_frames": len(waits),
            "previous_conflict_frame": before, "next_conflict_frame": after,
            "previous_gap_s": round((entry - before) / 20, 3),
            "next_gap_s": round((after - entry) / 20, 3),
            "traffic_near_at_entry": entry in conflict,
            "numeric_gap_is_engineering_proxy": True,
            "statutory_sufficient_gap_threshold": None,
            "physical_completion_claimed": False, "legal_verdict_claimed": False}


def measure_roundabout_context(measurement):
    return {"value": {"map_roads_read_back": [1, 2],
                      "entry_boundary_review_complete": False},
            "method": "measure_roundabout_context",
            "sources": {name: measurement["source_sha256"][name] for name in
                        ("roundabout-map-readback.json", "road.xodr")}}


def measure_yield_order(measurement):
    return {"value": {"first_entry_frame": measurement["first_entry_frame"],
                      "previous_conflict_frame": measurement["previous_conflict_frame"],
                      "next_conflict_frame": measurement["next_conflict_frame"],
                      "legal_yield_result": None},
            "method": "measure_yield_order",
            "sources": {name: measurement["source_sha256"][name] for name in
                        ("native-raw-actors.jsonl", "control-intent.jsonl",
                         "video_frames.jsonl")}}


def measure_gap_timing(measurement):
    return {"value": {"previous_gap_s": measurement["previous_gap_s"],
                      "next_gap_s": measurement["next_gap_s"],
                      "traffic_near_at_entry": measurement["traffic_near_at_entry"],
                      "statutory_threshold": None},
            "method": "measure_gap_timing",
            "sources": {name: measurement["source_sha256"][name] for name in
                        ("native-raw-actors.jsonl", "video_frames.jsonl")}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved analysis/result")
    measurement = analyze(attempt)
    config = json.loads((attempt / "config.json").read_text())
    source_hashes = measurement["source_sha256"]
    channels = attempt / "channels"
    if channels.exists():
        raise ValueError("Derived channels already exist")
    channels.mkdir()
    actor_rows = rows(attempt / "native-raw-actors.jsonl")
    frame_rows = rows(attempt / "video_frames.jsonl")
    for name, values in (("raw_ego_motion", [next(a for a in row["actors"] if a["role"] == "ego")
                                             for row in actor_rows]),
                         ("raw_circulating_motion", [[a for a in row["actors"] if a["role"] != "ego"]
                                                     for row in actor_rows]),
                         ("frame_join", frame_rows)):
        with (channels / (name + ".jsonl")).open("x") as stream:
            for frame, value in zip(frame_rows, values):
                stream.write(json.dumps({"time_s": frame["time_s"], "value": value}) + "\n")
    (channels / "roundabout_map.json").write_text(json.dumps({
        "roundabout_map": {"source_sha256": source_hashes["roundabout-map-readback.json"],
                           "source": "roundabout-map-readback.json"}}, indent=2) + "\n")
    for name, digest in source_hashes.items():
        if sha(attempt / name) != digest:
            raise ValueError("Original source changed during finalization: " + name)
    result = {"case_id": measurement["case_id"],
        "measured_values": {"entry_gap_diagnostic": measurement},
        "target_checks": [{"target": "source-observed entry timing relative to circulating actors",
            "requested": config["entry_release_s"],
            "measured": measurement["first_entry_frame"] / 20,
            "method": "first original ego road-1 frame; compare source traffic brackets",
            "tolerance": 2.0, "matched": abs(measurement["first_entry_frame"] / 20 -
                                              config["entry_release_s"]) <= 2.0,
            "physical_cause_confirmed": False, "cause_evidence": list(source_hashes)}],
        "setup_confirmed": False, "behavior_attempted": True,
        "maneuver_completed": False,
        "termination_reason": "Saved source timing measured; geometry, pixels, driver role and legal gap require original review",
        "physical_failure_flags": ["full_boundary_pixels_and_statutory_gap_unreviewed"],
        "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in CAMERAS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": ([{"name": name, "unit": "structured",
            "reference": "channels/" + name + ".jsonl"} for name in
            ("raw_ego_motion", "raw_circulating_motion", "frame_join")] +
            [{"name": "roundabout_map", "unit": "source_record",
              "reference": "channels/roundabout_map.json"}]),
        "realized_observables": {"entry_frame": {"value": measurement["first_entry_frame"],
            "unit": "frame", "method": "first original ego road-1 frame",
            "time_window": "600 original frames", "statistic": "first",
            "reference": "channels/raw_ego_motion.jsonl"}},
        "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c239014-saved-delivery-measurements-v1",
              "case_id": measurement["case_id"],
              "measurements": {"roundabout_context": measure_roundabout_context(measurement),
                               "yield_order": measure_yield_order(measurement),
                               "gap_timing": measure_gap_timing(measurement)},
              "diagnostic": measurement, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

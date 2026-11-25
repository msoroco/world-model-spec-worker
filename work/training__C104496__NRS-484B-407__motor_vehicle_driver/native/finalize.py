"""Finalize saved C104496 sources without inferring original visibility.

Synthetic fixture results are software diagnostics. The same joins reject a
capture with missing ray, road, motion, frame-map, or camera sources.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

FRAMES = 700
RATE = 20
VIDEOS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
          "driver_reference.mkv")
SOURCES = ("case-scope.json", "road.xodr", "trace.jsonl",
           "turn_history.jsonl", "analytic_sight.jsonl", "curve_context.json",
           "capture/evidence.jsonl", "video_frames.jsonl", *VIDEOS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def measure_crest_grade(scope, sight, context):
    """Saved authored grade and centerline ray clearance, with source limits."""
    margins = [value for row in sight for value in
               row["analytic_road_above_ray_m"] if value is not None]
    return {"road_kind": context["road_kind"],
            "authored_grade_height_m": scope["grade_height_m"],
            "minimum_analytic_road_above_ray_m": min(margins),
            "maximum_analytic_road_above_ray_m": max(margins),
            "sampled_ray_count": len(margins),
            "unavailable_ray_count": 2 * len(sight) - len(margins),
            "observer_road_distance_m": 152.4,
            "original_body_visibility_verified": False}


def measure_curve_or_crest(scope, sight, context):
    """Source-backed road type and authored centerline ray bounds."""
    west = [row["analytic_road_above_ray_m"][0] for row in sight
            if row["analytic_road_above_ray_m"][0] is not None]
    east = [row["analytic_road_above_ray_m"][1] for row in sight
            if row["analytic_road_above_ray_m"][1] is not None]
    return {"road_kind": context["road_kind"],
            "authored_road_sha256": context["authored_road_sha256"],
            "west_analytic_road_above_ray_range_m": [min(west), max(west)],
            "east_analytic_road_above_ray_range_m": [min(east), max(east)],
            "west_unavailable_samples": len(sight) - len(west),
            "east_unavailable_samples": len(sight) - len(east),
            "original_body_visibility_verified": False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain original finalization; use a fresh attempt")
    for name in (*SOURCES, "config.json", "construction.json"):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config, construction = read(attempt / "config.json"), read(attempt / "construction.json")
    scope, context = read(attempt / "case-scope.json"), read(attempt / "curve_context.json")
    case_id = config.get("selected_case_id", config.get("case_id"))
    if (case_id != construction.get("case_id") or case_id != scope.get("case_id") or
            case_id != context.get("case_id")):
        raise ValueError("Exact case or candidate source differs")
    if context.get("authored_road_sha256") != sha(attempt / "road.xodr"):
        raise ValueError("Authored road source hash differs")
    trace, turn, sight, evidence, mapping = (
        rows(attempt / name) for name in ("trace.jsonl", "turn_history.jsonl",
        "analytic_sight.jsonl", "capture/evidence.jsonl", "video_frames.jsonl"))
    if any(len(source) != FRAMES for source in (trace, turn, sight, evidence, mapping)):
        raise ValueError("Saved source frame counts differ")
    for index, (t, u, s, e, m) in enumerate(zip(trace, turn, sight, evidence, mapping)):
        frame = t.get("frame")
        time_s = index / RATE
        if (frame != u.get("frame") or frame != s.get("frame") or
                frame != e.get("original_frame") or frame != m.get("carla_frame") or
                m.get("native_frame") != frame or m.get("video_frame") != index or
                any(abs(row.get("time_s", -1) - time_s) > 1e-6
                    for row in (t, u, s, m)) or
                abs(e.get("recording_time_s", -1) - time_s) > 1e-6):
            raise ValueError("Saved trace/turn/ray/camera frame join differs")
        if (not isinstance(s.get("observer_stations_m"), list) or
                len(s["observer_stations_m"]) != 2 or
                len(s.get("analytic_road_above_ray_m", [])) != 2 or
                any(v is not None and (not isinstance(v, (int, float)) or
                    not math.isfinite(v)) for v in s["analytic_road_above_ray_m"])):
            raise ValueError("Missing finite authored two-direction ray source")
    synthetic = scope.get("format") == "c104496-synthetic-source-scope-v1"
    if synthetic and not (context.get("synthetic_diagnostic") is True and
                          scope.get("original_visibility_verified") is False):
        raise ValueError("Synthetic source scope is inconsistent")
    channels = attempt / "channels"
    channels.mkdir()
    recording = construction["recording_description"]
    stream_values = {
        "curve_geometry": lambda t, u, s, e, m: {"road_kind": context["road_kind"],
            "observer_stations_m": s["observer_stations_m"]},
        "grade_profile": lambda t, u, s, e, m: {"authored_grade_height_m": scope["grade_height_m"],
            "ego_z_m": e["ego"]["position_m"][2]},
        "reversal_motion": lambda t, u, s, e, m: {"heading_deg": u["heading_deg"],
            "phase": u["requested_motion_phase"], "body_vertices_m": u["body_vertices_m"]},
        "two_direction_visibility": lambda t, u, s, e, m: {
            "analytic_road_above_ray_m": s["analytic_road_above_ray_m"],
            "original_body_visibility_verified": False},
        "source_camera_views": lambda t, u, s, e, m: {
            "video_frame": m["video_frame"], "source_videos": list(VIDEOS),
            "synthetic_diagnostic": synthetic},
        "native_body_pose_control": lambda t, u, s, e, m: {
            "body_vertices_m": e["ego"]["body_vertices_m"],
            "position_m": e["ego"]["position_m"], "control": t["control"]},
        "camera_frame_join": lambda t, u, s, e, m: m,
    }
    recorded = []
    for channel in recording["channels"]:
        name = channel["name"]
        if name not in stream_values:
            raise ValueError("Unsupported C104496 recording channel: " + name)
        path = channels / (name + ".jsonl")
        with path.open("x") as stream:
            for t, u, s, e, m in zip(trace, turn, sight, evidence, mapping):
                stream.write(json.dumps({"time_s": m["time_s"],
                    "value": stream_values[name](t, u, s, e, m)},
                    allow_nan=False, separators=(",", ":")) + "\n")
        recorded.append({"name": name, "unit": channel["unit"],
                         "reference": "channels/" + path.name})
    for context_item in recording["context_inputs"]:
        name = context_item["name"]
        if name != "native_map_and_lanes":
            raise ValueError("Unsupported C104496 context: " + name)
        path = channels / (name + ".json")
        path.write_text(json.dumps({name: {"authored_road_sha256": sha(attempt / "road.xodr"),
            "source_kind": "synthetic_authored_geometry" if synthetic else "original_native",
            "native_map_readback_verified": not synthetic}}, allow_nan=False) + "\n")
        recorded.append({"name": name, "unit": context_item["unit"],
                         "reference": "channels/" + path.name})
    crest_value = measure_crest_grade(scope, sight, context)
    curve_value = measure_curve_or_crest(scope, sight, context)
    measurements = {
        "crest_grade_and_two_direction_sight": {"method": "measure_crest_grade",
            "value": crest_value, "sources": {name: sha(attempt / name) for name in
                ("case-scope.json", "analytic_sight.jsonl", "curve_context.json")}},
        "crest_demo_681ce_geometry": {"method": "measure_crest_grade",
            "value": crest_value, "sources": {name: sha(attempt / name) for name in
                ("case-scope.json", "analytic_sight.jsonl", "curve_context.json")}},
        "crest_demo_fa163_geometry": {"method": "measure_crest_grade",
            "value": crest_value, "sources": {name: sha(attempt / name) for name in
                ("case-scope.json", "analytic_sight.jsonl", "curve_context.json")}},
        "curve_or_crest_two_direction_sight": {"method": "measure_curve_or_crest",
            "value": curve_value, "sources": {name: sha(attempt / name) for name in
                ("case-scope.json", "analytic_sight.jsonl", "curve_context.json")}},
    }
    report = {"format": "c104496-saved-analysis-v1", "case_id": case_id,
        "measurements": measurements, "physical_acceptance_claimed": False,
        "legal_verdict_claimed": False, "synthetic_diagnostic": synthetic,
        "limitations": ["Authored centerline rays do not prove original CARLA body visibility,",
                        "camera recognition, physical reversal, or legal judgment."]}
    result = {"case_id": case_id, "measured_values": {"authored_grade_height_m":
        scope["grade_height_m"], "analytic_sight": curve_value},
        "target_checks": [{"target": "authored two-direction 500-foot centerline ray source",
            "requested": 2, "measured": 2, "method": "source-joined analytic sight rows",
            "tolerance": 0, "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["analytic_sight.jsonl", "road.xodr"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "full diagnostic 700-frame saved window",
        "physical_failure_flags": ["Original Native body visibility and maneuver unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": recording, "recording_evidence": recorded,
        "realized_observables": {},
        "provenance_kind": "synthetic_local_diagnostic" if synthetic else "original_native",
        "accepted": False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    (attempt / "result.json").write_text(json.dumps(result, indent=2,
                                                   allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

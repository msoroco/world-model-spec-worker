"""Saved-only Native result for all three exact highway roadside cases."""
import argparse
import hashlib
import json
from pathlib import Path

from finalize_saved import summarize

CHANNELS = ("drv.standing_or_parked", "st.roadway", "st.shoulder", "rel.occupies",
            "st.lane_width", "st.sight_distance", "rel.visible", "sig.hazard",
            "kin.velocity", "st.road_edge")
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_source(attempt, name):
    path = attempt / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def measure_roadside(measurement, attempt):
    sources = ("roadside-native.jsonl", "visibility-native.jsonl",
               "original-highway-survey.json", "video_frames.jsonl")
    return {"value": {"stopped_frames": len(measurement["stopped"]),
                      "on_pavement_frames": sum(row["pavement_overlap_m"] > 0 for row in measurement["stopped"]),
                      "minimum_residual_width_m": min(row["opposite_unobstructed_width_m"] for row in measurement["stopped"]),
                      "all_stopped_frames_clear_at_200ft_forward_proxy": all(row["clear_200ft_forward_proxy"] for row in measurement["stopped"]),
                      "all_stopped_frames_clear_at_200ft_backward_proxy": all(row["clear_200ft_backward_proxy"] for row in measurement["stopped"]),
                      "injected_failure_frames": sum(row["failure_active"] for row in measurement["stopped"]),
                      "legal_result": None},
            "method": "measure_roadside",
            "sources": {name: sha(attempt / name) for name in sources}}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / "result.json").exists():
        raise ValueError("Retain prior saved roadside measurement")
    for name in ("config.json", "roadside-native.jsonl", "visibility-native.jsonl",
                 "original-highway-survey.json", "video_frames.jsonl", "trace.jsonl",
                 *(view + ".mkv" for view in CAMERAS)):
        require_source(attempt, name)
    config = json.loads((attempt / "config.json").read_text())
    case = config.get("selected_case_id")
    if not case or case != config.get("case_id"):
        raise ValueError("Selected exact roadside case differs")
    survey = json.loads((attempt / "original-highway-survey.json").read_text())
    diagnostic = survey.get("source_kind") == "synthetic_native_sample"
    measurement = summarize(attempt, case, diagnostic=diagnostic)
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    original_rows = [json.loads(line) for line in (attempt / "roadside-native.jsonl").read_text().splitlines()]
    views = [json.loads(line) for line in (attempt / "visibility-native.jsonl").read_text().splitlines()]
    left, right = survey["pavement_left_y_m"], survey["pavement_right_y_m"]
    for name in CHANNELS:
        with (channels / (name + ".jsonl")).open("x") as stream:
            for body, view in zip(original_rows, views):
                value = {"native_frame": body["native_frame"],
                         "vehicle_id": body["vehicle_id"], "other_vehicle_id": body["other_vehicle_id"],
                         "speed_mps": body["speed_mps"], "vehicle_y_m": body["y_m"],
                         "half_width_m": body["bbox_half_width_m"],
                         "pavement_edges_y_m": [left, right],
                         "district": survey["district"],
                         "forward_200ft_rays": view["approaches"]["forward"]["ray_clear"],
                         "backward_200ft_rays": view["approaches"]["backward"]["ray_clear"],
                         "failure_active": body.get("failure_active") is True,
                         "diagnostic_fixture": diagnostic}
                stream.write(json.dumps({"time_s": body["t_s"], "value": value}) + "\n")
    observed = measure_roadside(measurement, attempt)
    result = {"case_id": case,
              "measured_values": {"roadside_stop": {"value": observed["value"],
                                   "source_hashes": observed["sources"], "legal_result": None}},
              "target_checks": [{"target": "sourced roadside stopped position and sight",
                  "requested": config["stop_mode"], "measured": observed["value"],
                  "method": "saved original trace, survey, ray and frame join",
                  "tolerance": 0, "matched": False, "physical_cause_confirmed": False,
                  "cause_evidence": list(observed["sources"])}],
              "setup_confirmed": False, "behavior_attempted": True,
              "maneuver_completed": False,
              "termination_reason": "Saved roadside measurements complete; physical review pending",
              "physical_failure_flags": ["original_highway_survey_and_sight_review_pending"],
              "trace_reference": "trace.jsonl",
              "video_references": [view + ".mkv" for view in CAMERAS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": config["recording_description"],
              "recording_evidence": [{"name": name, "unit": "structured",
                  "reference": "channels/" + name + ".jsonl"} for name in CHANNELS],
              "realized_observables": {"on_pavement_frames": {"value": observed["value"]["on_pavement_frames"],
                  "unit": "frames", "method": "saved source-bound footprint overlap",
                  "time_window": "600 joined Native frames", "statistic": "stopped frames with pavement overlap",
                  "reference": "channels/rel.occupies.jsonl"}},
              "accepted": False, "legal_verdict_claimed": False}
    write_result(attempt, result)
    report = {"format": "c178965-saved-roadside-measurements-v1", "case_id": case,
              "measurements": {"roadside": observed},
              "diagnostic": {"source_sha256": measurement["source_sha256"],
                             "diagnostic_fixture": diagnostic},
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    output.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

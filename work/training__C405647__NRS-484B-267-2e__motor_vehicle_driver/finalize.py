"""Finalize saved emergency-lane sources without inferring legal possibility."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import VIDEOS, measure, rows
from source_review import SOURCES


CHANNELS = (
    "drv.responding_emergency", "st.lane", "st.lane_adjacency",
    "rel.occupies", "drv.lane_change_feasible", "env.precipitation",
    "env.wet_road", "st.obstruction", "drv.queue_behind",
    "dev.human_direction",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def measure_emergency_response(measured, config):
    return {"active_approach_frames": measured["active_approach_frames"],
            "active_adjacent_frames": measured["active_adjacent_frames"],
            "active_nonadjacent_frames": measured["active_nonadjacent_frames"],
            "moving_frames": measured["moving_frames"],
            "visible_hand_signal_frames": measured["visible_hand_signal_frames"],
            "visible_officer_direction_frames": measured["visible_officer_direction_frames"],
            "requested_response": config["requested_response"],
            "lane_change_possible": None, "lane_change_safe": None,
            "officer_override_applies": None, "legal_result": None}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / "result.json").exists() and
            not (attempt / "channels").exists(), "Retain original saved finalization")
    for name in ("config.json", "construction.json", "trace.jsonl", "video_frames.jsonl",
                 "emergency-native.jsonl", *VIDEOS):
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    case_id = config["case_id"]
    require(case_id == construction["case_id"], "Saved exact case differs")
    review = json.loads((attempt / "emergency-review.json").read_text())
    diagnostic = review.get("review_kind") == "synthetic_diagnostic"
    measured = measure(attempt, case_id, diagnostic=diagnostic)
    trace = rows(attempt / "emergency-native.jsonl")
    lamps = json.loads((attempt / "lamp-pixel-review.json").read_text())["frames"]
    signals = json.loads((attempt / "signal-pixel-review.json").read_text())["frames"]
    channel_defs = construction["recording_description"]["channels"]
    require({c["name"] for c in channel_defs} == set(CHANNELS),
            "Exact mandatory channel implementation differs")
    value = {
        "drv.responding_emergency": lambda p, l, s: {
            "actor_id": p["emergency"]["actor_id"],
            "qualifying_lamps_visible": l["qualifying_flashes_visible"],
            "vehicle_authority_source_sha256": measured["source_join"]["source_sha256"]["vehicle_authorization"]},
        "st.lane": lambda p, l, s: p["emergency"]["lane_id"],
        "st.lane_adjacency": lambda p, l, s: {"adjacent": [-2], "nonadjacent": [-3]},
        "rel.occupies": lambda p, l, s: p["ego"]["lane_id"],
        "drv.lane_change_feasible": lambda p, l, s: {
            "status": "unverified", "possible": None, "safe": None},
        "env.precipitation": lambda p, l, s: p.get("weather_precipitation"),
        "env.wet_road": lambda p, l, s: p.get("weather_wetness"),
        "st.obstruction": lambda p, l, s: p.get("road_obstruction_observed"),
        "drv.queue_behind": lambda p, l, s: {
            "traffic_actor_observed": p.get("traffic") is not None,
            "traffic_actor": p.get("traffic")},
        "dev.human_direction": lambda p, l, s: {
            "officer_direction_visible": s["officer_direction_visible"],
            "review_source_sha256": measured["source_join"]["source_sha256"]["officer_direction"]},
    }
    channel_dir = attempt / "channels"
    channel_dir.mkdir()
    recording_evidence = []
    for channel in channel_defs:
        name = channel["name"]
        path = channel_dir / (name + ".jsonl")
        with path.open("x") as stream:
            for p, l, s in zip(trace, lamps, signals):
                stream.write(json.dumps({"time_s": p["t_s"],
                                         "value": value[name](p, l, s)},
                                        allow_nan=False) + "\n")
        recording_evidence.append({"name": name, "unit": channel["unit"],
                                   "reference": "channels/" + path.name})
    response = measure_emergency_response(measured, config)
    source_names = ("emergency-review.json", "video_frames.jsonl",
                    "emergency-native.jsonl", "lamp-pixel-review.json",
                    "signal-pixel-review.json", "trace.jsonl",
                    *("source_context/" + name + ".txt" for name in SOURCES),
                    *VIDEOS)
    report = {"format": "c405647-2e-saved-analysis-v1", "case_id": case_id,
              "measurements": {"emergency_lane_response": {
                  "method": "measure_emergency_response", "value": response,
                  "sources": {name: digest(attempt / name) for name in source_names}}},
              "source_join": measured["source_join"],
              "physical_acceptance_claimed": False, "legal_verdict_claimed": False}
    requested_lane = -3 if config["requested_response"] == "move_nonadjacent" else -2
    observed_lane = trace[-1]["ego"]["lane_id"]
    result = {"case_id": case_id, "measured_values": response,
              "target_checks": [{"target": "requested ego lane engineering control",
                                 "requested": requested_lane, "measured": observed_lane,
                                 "method": "original saved lane readback and frame join",
                                 "tolerance": 0, "matched": requested_lane == observed_lane,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": list(source_names)}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "full 600-frame saved diagnostic interval",
              "physical_failure_flags": ["Original Native activation, safety and officer review pending"],
              "trace_reference": "trace.jsonl", "video_references": list(VIDEOS),
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": recording_evidence, "realized_observables": {},
              "provenance_kind": "synthetic_local_diagnostic" if diagnostic else "original_native",
              "accepted": False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

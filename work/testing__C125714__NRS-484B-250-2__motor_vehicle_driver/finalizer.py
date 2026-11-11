"""Saved-only subsection-2 entry analysis; physical/legal acceptance stays open."""
import argparse
import hashlib
import json
from pathlib import Path

from entry_measurements import analyze

CAMERAS = ("overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")
PREFIX = "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__"
PRIMARY = PREFIX + "source_verified_other_right_near_time"


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measurement(report):
    """Keep measurements and legal uncertainty together with original hashes."""
    return {
        "method": "first complete Native body intersection with sourced crossing polygon",
        "first_body_entry": report["first_body_entry"],
        "ego_minus_other_entry_time_s": report["ego_minus_other_entry_time_s"],
        "other_is_to_ego_right": report["other_is_to_ego_right"],
        "geometric_yield_candidate": report["geometric_yield_candidate"],
        "approximately_same_time_judgment": "unresolved; no numeric legal threshold",
        "right_of_way_judgment": "unresolved",
        "source_hashes": report["sources"],
    }


def measure_control(attempt, report, case_id):
    history = [json.loads(line) for line in (attempt / "crossing_history.jsonl").read_text().splitlines() if line.strip()]
    controls = [json.loads(line) for line in (attempt / "controller_history.jsonl").read_text().splitlines() if line.strip()]
    if len(history) < 2 or len(controls) != len(history):
        raise ValueError("Incomplete original yield controller history")
    entered = False
    holds, releases = 0, 0
    for row, state in zip(history, controls):
        if state.get("frame") != row.get("frame") or abs(state.get("time_s", -1) - row.get("time_s", -2)) > 1e-4:
            raise ValueError("Original yield controller frame/time join failed")
        inside = state.get("other_inside_before_tick")
        seen = state.get("other_entered_once")
        ego = state.get("ego_control")
        if type(inside) is not bool or type(seen) is not bool or not isinstance(ego, dict) or type(ego.get("hold")) is not bool:
            raise ValueError("Missing measured yield controller state")
        entered = entered or inside
        if seen is not entered:
            raise ValueError("Other-entry controller state changed")
        if case_id == PRIMARY and ego["hold"] is not (not seen):
            raise ValueError("Near-time controller release differs from first other entry")
        holds += ego["hold"]
        releases += not ego["hold"]
    return {"method": "measure_control",
            "value": {"controller_frames": len(controls), "ego_held_frames": holds,
                      "ego_released_frames": releases, "other_entry_seen": entered,
                      "yield_judgment": "unresolved"},
            "sources": {name: _sha(attempt / name) for name in
                        ("controller_history.jsonl", "crossing_history.jsonl", "video_frames.jsonl")}}


def measure_body_entry_timing(report):
    return {"method": "measure_body_entry_timing",
            "value": {"first_body_entry": report["first_body_entry"],
                      "ego_minus_other_entry_time_s": report["ego_minus_other_entry_time_s"],
                      "approximately_same_time_judgment": "unresolved"},
            "sources": report["sources"]}


def measure_approach_side(report):
    return {"method": "measure_approach_side",
            "value": {"other_is_to_ego_right": report["other_is_to_ego_right"],
                      "geometric_yield_candidate": report["geometric_yield_candidate"],
                      "right_of_way_judgment": "unresolved"},
            "sources": {"road_geometry.json": report["sources"]["road_geometry.json"]}}


def measure_device_exclusion(geometry, report):
    return {"method": "measure_device_exclusion",
            "value": {"official_device_controls_crossing": False,
                      "inventory_source": geometry["device_inventory_source"],
                      "subsection_4_qualification": "unresolved"},
            "sources": {"road_geometry.json": report["sources"]["road_geometry.json"]}}


def finalize(attempt: Path, output: Path):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / "result.json").exists() or (attempt / "channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    required = ("config.json", "road_geometry.json", "crossing_history.jsonl",
                "controller_history.jsonl",
                "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl", *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError("Missing required source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    case_id = config.get("selected_case_id", "")
    if not case_id.startswith(PREFIX) or config.get("law_id") != "NRS-484B-250-2" or config.get("cell_id") != "C125714":
        raise ValueError("Exact C125714 subsection-2 case required")
    if not isinstance(config.get("recording_description"), dict):
        raise ValueError("Recording description required")
    report = analyze(attempt)
    if not all(report["first_body_entry"].values()):
        raise ValueError("Both participants must have original body entry measurements")
    geometry = json.loads((attempt / "road_geometry.json").read_text())
    device_review = geometry.get("device_review")
    if not isinstance(device_review, dict) or device_review.get("official_device_controls_crossing") is not False:
        raise ValueError("Missing reviewed uncontrolled crossing device result")
    control = measure_control(attempt, report, case_id)
    channels = attempt / "channels"
    channels.mkdir()
    payload = measurement(report)
    (channels / "entry_context.json").write_text(json.dumps({"entry_context": payload}, indent=2, allow_nan=False) + "\n")
    (channels / "yield_control.json").write_text(json.dumps(control, indent=2, allow_nan=False) + "\n")
    (channels / "yield_control.jsonl").write_text("".join(json.dumps({"time_s": row["time_s"],
        "value": {"frame": row["frame"], "hold": row["ego_control"]["hold"]}},
        allow_nan=False) + "\n" for row in
        (json.loads(line) for line in (attempt / "controller_history.jsonl").read_text().splitlines() if line.strip())))
    measurements = {
        "body_entry_timing": measure_body_entry_timing(report),
        "approach_side": measure_approach_side(report),
        "device_exclusion_context": measure_device_exclusion(geometry, report),
        "yield_control_attempt": control,
    }
    result = {
        "case_id": case_id,
        "measured_values": {"entry_delta_s": report["ego_minus_other_entry_time_s"],
                            "other_is_to_ego_right": report["other_is_to_ego_right"]},
        "target_checks": [{
            "target": "both_bodies_enter_sourced_crossing", "requested": True,
            "measured": True, "method": payload["method"], "tolerance": 0,
            "matched": True, "physical_cause_confirmed": False,
            "cause_evidence": ["crossing_history.jsonl", "road_geometry.json", "video_frames.jsonl"],
        }],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "Saved original-source entry analysis; physical and legal review pending",
        "physical_failure_flags": ["statutory crossing identity, approximate time, control devices and yielding unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(CAMERAS),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["recording_description"],
        "recording_evidence": [{"name": "entry_context", "unit": "structured record",
                                "reference": "channels/entry_context.json"},
                               {"name": "yield_control", "unit": "structured record",
                                "reference": "channels/yield_control.jsonl"}],
        "source_evidence_hashes": {**report["sources"],
                                   "controller_history.jsonl": _sha(attempt / "controller_history.jsonl")},
        "capture_evidence_sha256": _sha(attempt / "capture/evidence.jsonl"),
        "realized_observables": {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({"format": "worker-median-entry-saved-analysis",
                                  "case_id": case_id, "measurement": payload,
                                  "measurements": measurements,
                                  "physical_acceptance_claimed": False}, indent=2,
                                 allow_nan=False) + "\n")
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

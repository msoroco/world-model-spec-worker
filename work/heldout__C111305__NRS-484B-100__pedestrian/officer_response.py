"""Source-bound observation of response to an officer's timed direction.

This records motion only. Officer authority, lawful order and willfulness remain
independent source and legal review questions.
"""
from __future__ import annotations
import json
import hashlib
from pathlib import Path


def _load(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("missing required source: " + str(p))
    return json.loads(p.read_text())


def measure(context_path, direction_path, motion_path, *, expected_actor, expected_command):
    context, direction, motion = (_load(p) for p in (context_path, direction_path, motion_path))
    if context.get("actor_role") != expected_actor:
        raise ValueError("actor role differs from exact case")
    if context.get("officer_role") != "police_officer" or not context.get("officer_id"):
        raise ValueError("officer role or identity missing")
    if not context.get("duty_source") or not context.get("lawfulness_source"):
        raise ValueError("officer duty and order-lawfulness source references required")
    if context.get("legal_conclusion") or context.get("willfulness_conclusion"):
        raise ValueError("fixture may not assert legal or willfulness conclusion")
    if direction.get("officer_id") != context["officer_id"] or direction.get("subject_id") != context.get("subject_id"):
        raise ValueError("direction is not source-bound to this officer and subject")
    if direction.get("command") != expected_command or expected_command not in ("stop", "proceed"):
        raise ValueError("direction differs from exact case")
    # The selected pedestrian witness calls for a particular wait location and
    # release direction. These fields identify what was attempted; they do not
    # establish that the officer had authority or that the subject perceived it.
    if direction.get("recipient_id") != context["subject_id"]:
        raise ValueError("officer direction recipient differs from subject")
    if not direction.get("wait_location_source") or not direction.get("exact_direction_text"):
        raise ValueError("exact wait location and direction source required")
    if direction.get("communication_modality") not in ("visual", "auditory", "both"):
        raise ValueError("communication modality must be sourced")
    if not direction.get("opportunity_source") or not direction.get("communication_source"):
        raise ValueError("communication and opportunity sources required")
    if direction.get("actual_perception") is not None:
        raise ValueError("actual perception cannot be inferred from fixture")
    frame = direction.get("frame")
    if type(frame) is not int or frame < 0 or not direction.get("indication_source"):
        raise ValueError("timed officer indication source missing")
    rows = motion.get("frames")
    if not isinstance(rows, list) or len(rows) < 3:
        raise ValueError("retained subject motion span missing")
    indices = [r.get("frame") for r in rows]
    if any(type(i) is not int for i in indices) or indices != sorted(set(indices)):
        raise ValueError("motion frame identities must be unique and ordered")
    if not (indices[0] <= frame < indices[-1]):
        raise ValueError("motion does not bracket direction and response")
    if any(r.get("subject_id") != context["subject_id"] for r in rows):
        raise ValueError("motion subject differs from direction subject")
    if any(type(r.get("speed_mps")) not in (int, float) or r["speed_mps"] < 0 for r in rows):
        raise ValueError("invalid original subject speed sample")
    following = [r for r in rows if r["frame"] > frame]
    if len(following) < 2:
        raise ValueError("at least two post-indication motion samples required")
    # Descriptive engineering observation, not a legal compliance threshold.
    stopped = any(r["speed_mps"] <= 0.1 for r in following)
    moving = any(r["speed_mps"] > 0.5 for r in following)
    if expected_command == "stop":
        response = "stopped_after_indication" if stopped else "no_observed_stop"
    else:
        response = "moved_after_indication" if moving else "no_observed_movement"
    return {"actor_role": expected_actor, "subject_id": context["subject_id"],
            "officer_id": context["officer_id"], "command": expected_command,
            "recipient_id": direction["recipient_id"],
            "exact_direction_text": direction["exact_direction_text"],
            "wait_location_source": direction["wait_location_source"],
            "communication_modality": direction["communication_modality"],
            "communication_source": direction["communication_source"],
            "opportunity_source": direction["opportunity_source"],
            "indication_frame": frame, "first_motion_frame": indices[0],
            "last_motion_frame": indices[-1], "post_indication_samples": len(following),
            "min_post_speed_mps": min(r["speed_mps"] for r in following),
            "max_post_speed_mps": max(r["speed_mps"] for r in following),
            "observed_response": response,
            "source_refs": [str(context_path), str(direction_path), str(motion_path)],
            "legal_conclusion": None, "willfulness_conclusion": None,
            "actual_perception": None}


def _required(root, name):
    path = Path(root) / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze_saved(root):
    """Join only retained original sources; write derived channels after checks."""
    root = Path(root)
    from runner import check_config
    config = json.loads(_required(root, "config.json").read_text())
    command, _ = check_config(config)
    source_names = ("officer_context.json", "officer_direction.json", "subject_motion.json",
                    "subject_motion_history.jsonl", "video_frames.jsonl", "trace.jsonl")
    originals = {name: _required(root, name) for name in source_names}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        _required(root, name + ".mkv")
    observed = measure(originals["officer_context.json"], originals["officer_direction.json"],
                       originals["subject_motion.json"], expected_actor="pedestrian", expected_command=command)
    mapping = _rows(originals["video_frames.jsonl"])
    trace = _rows(originals["trace.jsonl"])
    history = _rows(originals["subject_motion_history.jsonl"])
    if len(mapping) < 3 or len(mapping) != len(trace) or len(trace) != len(history):
        raise ValueError("Original pedestrian frame-map, trace and motion lengths differ")
    for index, (fm, tick, row) in enumerate(zip(mapping, trace, history)):
        if (fm.get("video_frame") != index or fm.get("carla_frame") != tick.get("frame")
                or tick.get("frame") != row.get("frame") or fm.get("time_s") != tick.get("time_s")
                or tick.get("time_s") != row.get("time_s") or row.get("subject_id") != observed["subject_id"]):
            raise ValueError("Original pedestrian frame join differs")
    if json.loads(originals["subject_motion.json"].read_text())["frames"] != history:
        raise ValueError("Original pedestrian motion JSON and JSONL differ")
    if observed["indication_frame"] not in {row["frame"] for row in history}:
        raise ValueError("Timed original indication absent from frame map")
    channels = {
        "subject_speed_mps": [(row["frame"], row["time_s"], row["speed_mps"]) for row in history],
        "officer_direction": [(row["frame"], row["time_s"], int(row["frame"] >= observed["indication_frame"])) for row in history],
    }
    for name, values in channels.items():
        (root / (name + ".jsonl")).write_text("".join(json.dumps({"frame": frame, "time_s": time_s, "value": value}) + "\n"
                                                   for frame, time_s, value in values))
    return {"format": "worker-analysis-report", "case_id": config["selected_case_id"],
            "measurements": {"officer_response": {"method": "analyze_saved",
                                               "value": observed,
                                               "sources": {name: _sha(path) for name, path in originals.items()}}},
            "legal_acceptance_claimed": False, "physical_acceptance_claimed": False}


def saved_result(root, report):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    observed = report["measurements"]["officer_response"]["value"]
    history = _rows(root / "subject_motion_history.jsonl")
    post_times = [row["time_s"] for row in history if row["frame"] > observed["indication_frame"]]
    contexts = []
    for name, original_name in (("officer_context", "officer_context.json"),
                                ("officer_direction_context", "officer_direction.json"),
                                ("subject_motion_context", "subject_motion.json"),
                                ("subject_motion_history", "subject_motion_history.jsonl")):
        original = root / original_name
        value = _rows(original) if original.suffix == ".jsonl" else json.loads(original.read_text())
        derived = root / (name + "-recorded.json")
        if derived.exists():
            raise ValueError("Retain prior derived pedestrian context")
        derived.write_text(json.dumps({name: value}) + "\n")
        contexts.append({"name": name, "unit": "structured record", "reference": derived.name,
                         "sha256": _sha(derived)})
    return {"case_id": report["case_id"], "measured_values": {"officer_response": observed},
            "target_checks": [{"target": "timed officer indication and observed pedestrian response",
                               "requested": config["case"]["intended_observed_response"],
                               "measured": observed["observed_response"],
                               "method": "source-bound indication and post-indication original pedestrian motion",
                               "tolerance": None,
                               "matched": observed["observed_response"] == config["case"]["intended_observed_response"],
                               "physical_cause_confirmed": False,
                               "cause_evidence": "Original gesture and motion; authority, perception and willfulness require review"}],
            "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": False,
            "termination_reason": "Saved source measurement complete; physical and legal outcome unverified",
            "physical_failure_flags": {"gesture_visibility_unverified": True,
                                       "officer_authority_unverified": True,
                                       "pedestrian_perception_unverified": True},
            "trace_reference": "trace.jsonl",
            "video_references": [name + ".mkv" for name in ("overview", "approach", "reference_corner", "driver_reference")],
            "video_frame_map_reference": "video_frames.jsonl",
            "recording_description": config["case"]["recording_description"],
            "recording_evidence": [
                *[{"name": name, "unit": unit, "reference": name + ".jsonl",
                   "sha256": _sha(root / (name + ".jsonl"))}
                  for name, unit in (("subject_speed_mps", "m/s"), ("officer_direction", "boolean"))],
                *contexts],
            "realized_observables": {
                "subject_speed_mps": {"unit": "m/s", "method": "original pedestrian velocity after indication",
                                      "time_window": "post-indication original frames", "statistic": "min",
                                      "reference": "subject_speed_mps.jsonl", "value": observed["min_post_speed_mps"],
                                      "sample_window_s": [min(post_times), max(post_times)]},
                "officer_direction": {"unit": "boolean", "method": "original walker arm activation at indication frame",
                                      "time_window": "all original frames", "statistic": "event",
                                      "reference": "officer_direction.jsonl", "value": 1,
                                      "sample_window_s": [history[0]["time_s"], history[-1]["time_s"]]}},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}


def _saved_main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze_saved(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior analysis report")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, saved_result(args.attempt, report))


def main():
    import argparse
    import sys
    if "--attempt" in sys.argv:
        return _saved_main()
    ap=argparse.ArgumentParser()
    ap.add_argument("--context",required=True)
    ap.add_argument("--direction",required=True)
    ap.add_argument("--motion",required=True)
    ap.add_argument("--actor",required=True)
    ap.add_argument("--command",choices=("stop","proceed"),required=True)
    ap.add_argument("--output",required=True)
    a=ap.parse_args()
    result=measure(a.context,a.direction,a.motion,expected_actor=a.actor,expected_command=a.command)
    Path(a.output).write_text(json.dumps(result,indent=2)+"\n")
if __name__ == "__main__": main()

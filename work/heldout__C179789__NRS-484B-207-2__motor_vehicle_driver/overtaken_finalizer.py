"""Saved-only finalization of the observed overtaken-driver comparison.

The original body, trace, frame map and collision-ray records determine the
measurement. A clear ray is a simulated line-of-sight proxy, not proof of
human observation or a legal verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from overtaken_response import measure_audible_saved, measure_observed_saved, verify_saved_sources


CASE_ID = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__observed_gives_way_holds_speed"
SOURCES = ("overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl")
AUDIBLE_CASE_ID = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__gives_way_holds_speed"
SIGNAL_SOURCES = ("signal_command_original.jsonl", "signal_audio_envelope_original.jsonl")


def measure_response(root, case_id=CASE_ID):
    root = Path(root)
    if case_id == AUDIBLE_CASE_ID:
        return measure_audible_saved(*(root / name for name in SOURCES + SIGNAL_SOURCES))
    return measure_observed_saved(*(root / name for name in SOURCES))


def measure_right_shift(observed):
    return observed["max_right_shift_m"]


def measure_speed_delta(observed):
    return observed["max_precompletion_speed_delta_mps"]


def measure_pass_completion(observed):
    return observed["pass_complete_frame"]


def analyze(attempt):
    root = Path(attempt)
    config_path = root / "config.json"
    if not config_path.is_file():
        raise ValueError("Missing required source: config.json")
    config = json.loads(config_path.read_text())
    case_id = config.get("selected_case_id")
    if (case_id not in (CASE_ID, AUDIBLE_CASE_ID) or
        (config.get("law_id"),config.get("cell_id"),config.get("actor")) !=
        ("NRS-484B-207-2", "C179789", "motor_vehicle_driver")):
        raise ValueError("Wrong exact overtaken-driver finalizer identity")
    observed = measure_response(root, case_id)
    return {"format":"worker-analysis-report", "case_id":case_id,
            "measurements":{"overtaken_response":{
                "method":"measure_response", "value":observed,
                "sources":observed["source_sha256"]},
                "right_shift_m":{"method":"measure_right_shift",
                    "value":measure_right_shift(observed),"sources":observed["source_sha256"]},
                "speed_delta_mps":{"method":"measure_speed_delta",
                    "value":measure_speed_delta(observed),"sources":observed["source_sha256"]},
                "pass_complete_frame":{"method":"measure_pass_completion",
                    "value":measure_pass_completion(observed),"sources":observed["source_sha256"]}},
            "limitations":observed["limitations"],
            "physical_acceptance_claimed":False,
            "legal_acceptance_claimed":False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    description = config.get("case", {}).get("recording_description")
    if not isinstance(description, dict):
        raise ValueError("Selected recording description missing")
    observed = report["measurements"]["overtaken_response"]["value"]
    case_id = config.get("selected_case_id")
    if report.get("case_id") != case_id or case_id not in (CASE_ID, AUDIBLE_CASE_ID):
        raise ValueError("Saved result case identity differs")
    verified = verify_saved_sources(*(root / name for name in SOURCES))
    rows = verified["frames"]
    evidence = []
    for key, unit in (("right_offset_m", "m"), ("speed_mps", "m/s")):
        name = "subject_" + key + ".jsonl"
        path = root / name
        if path.exists():
            raise ValueError("Retain prior derived channel: " + name)
        path.write_text("".join(json.dumps({"frame":row["frame"],
            "time_s":row["time_s"], "value":row[key]}, allow_nan=False)+"\n"
            for row in rows))
        evidence.append({"name":"subject_"+key,"unit":unit,"reference":name,
                         "sha256":hashlib.sha256(path.read_bytes()).hexdigest()})
    audible = case_id == AUDIBLE_CASE_ID
    return {"case_id":case_id,
            "measured_values":{"overtaken_response":observed},
            "target_checks":[
                {"target":"rightward response after original signal command" if audible else "rightward response after original visibility",
                 "requested":config.get("target_right_offset_m",1),
                 "measured":observed["max_right_shift_m"],
                 "method":"original body pose against road tangent",
                 "tolerance":None,"matched":False,
                 "physical_cause_confirmed":False,
                 "cause_evidence":"original generated signal rows and actor body/trace sources" if audible else "original collision rays and actor body/trace sources"},
                {"target":"speed hold until body pass completion",
                 "requested":0,"measured":observed["max_precompletion_speed_delta_mps"],
                 "method":"original subject velocity joined to body pass completion",
                 "tolerance":None,"matched":False,
                 "physical_cause_confirmed":False,
                 "cause_evidence":"original trace and actor body sources"}],
            "setup_confirmed":False,"behavior_attempted":True,
            "maneuver_completed":False,
            "termination_reason":"Saved source-derived response measured; hearing and physical outcome unverified" if audible else "Saved source-derived response measured; physical outcome unverified",
            "physical_failure_flags":{"detection_validated":False},
            "trace_reference":"trace.jsonl",
            "video_references":["overview.mkv","approach.mkv",
                                "reference_corner.mkv","driver_reference.mkv"],
            "video_frame_map_reference":"video_frames.jsonl",
            "recording_description":description,
            "recording_evidence":evidence,
            "realized_observables":{
                "subject_right_offset_m":{"unit":"m","method":"original actor pose/road tangent",
                    "time_window":"first visibility until body pass completion","statistic":"max shift",
                    "reference":"subject_right_offset_m.jsonl",
                    "value":observed["max_right_shift_m"],
                    "sample_window_s":[rows[0]["time_s"],rows[-1]["time_s"]]},
                "subject_speed_mps":{"unit":"m/s","method":"original actor velocity",
                    "time_window":"first visibility until body pass completion","statistic":"max precompletion delta",
                    "reference":"subject_speed_mps.jsonl",
                    "value":observed["max_precompletion_speed_delta_mps"],
                    "sample_window_s":[rows[0]["time_s"],rows[-1]["time_s"]]}},
            "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior analysis report")
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == "__main__":
    main()

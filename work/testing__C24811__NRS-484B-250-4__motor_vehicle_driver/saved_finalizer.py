"""Saved-only C24811 processing from retained original Native sources.

This module derives observations and source hashes. It does not establish
statutory inoperability, cautious motion, yielding or physical acceptance.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from blind_signal_measurements import analyze_exact_case
from source_cameras import CAMERAS


REQUIRED = ("config.json", "trace.jsonl", "vehicle_signal_history.jsonl",
            "video_frames.jsonl", "junction_context.json", "capture/evidence.jsonl",
            "capture/manifest.json", "capture-seal.json",
            *(name+".mkv" for name in CAMERAS))
PREFIX = "testing__C24811__NRS-484B-250-4__motor_vehicle_driver__"
MEASUREMENT_INPUTS = ("vehicle_signal_history.jsonl", "video_frames.jsonl",
                      "junction_context.json")


def measure_signal_states(report, context):
    return {"state": report["expected_governing_signal_state"],
            "governing_head_ids": report["signal_head_ids"],
            "installed_uncovered_context": all(
                head["installed"] and head["uncovered"]
                for head in context["signal_heads"])}


def measure_stop_reference(report, context):
    return "marked_stop_line" if context["stop_line_exists"] else "none"


def measure_ego_full_halt(report, context):
    return report["ego_stopped_before_entry_observed"]


def measure_prior_stop(report, context):
    return report["distinct_other_stopped_earlier_observed"]


def measure_intersection_occupancy(report, context):
    return {"first_body_entry": report["first_body_entry"],
            "occupant_inside_at_ego_entry":
                report["distinct_occupant_inside_at_ego_entry_observed"]}


def measure_post_stop_motion(report, context):
    stop = report["first_full_halt"]["ego"]
    later = [row for row in report["samples"]
             if stop is not None and row["frame"] > stop["frame"]]
    return {"ego_full_halt_frame": stop["frame"] if stop else None,
            "samples_after_halt": len(later),
            "first_post_halt_speed_mps": later[0]["ego"]["speed_mps"]
                if later else None,
            "complete_capture_samples": len(report["samples"])}


def measure_sight_context(report, context):
    return {"occluder_geometry_source": context["occluder_geometry_source"],
            "sight_ray_source": context["sight_ray_source"],
            "signal_head_video_source": context["signal_head_video_source"]}


MEASUREMENT_METHODS = {
    "signal_states": measure_signal_states,
    "stop_reference": measure_stop_reference,
    "ego_full_halt": measure_ego_full_halt,
    "prior_stop": measure_prior_stop,
    "intersection_occupancy": measure_intersection_occupancy,
    "post_stop_motion": measure_post_stop_motion,
    "sight_context": measure_sight_context,
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _video_frames(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames",
        "-select_streams", "v:0", "-show_entries", "stream=codec_name,nb_read_frames",
        "-of", "json", str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1 or streams[0].get("codec_name") != "ffv1":
        raise ValueError("Original FFV1 source video required")
    count = int(streams[0].get("nb_read_frames", -1))
    if count <= 0:
        raise ValueError("Complete original video frames required")
    return count


def validate_sources(attempt):
    attempt = Path(attempt)
    for name in REQUIRED:
        if not (attempt/name).is_file():
            raise ValueError("Missing required source: " + name)
    cfg = json.loads((attempt/"config.json").read_text())
    case_id = cfg.get("selected_case_id")
    if (cfg.get("cell_id") != "C24811" or cfg.get("law_id") != "NRS-484B-250-4" or
            not isinstance(case_id, str) or not case_id.startswith(PREFIX)):
        raise ValueError("Wrong C24811 saved capture identity")
    state = cfg.get("operative_signal_state") if case_id.endswith("__operative_signal") else None
    report = analyze_exact_case(attempt, case_id, operative_state=state)
    history = _rows(attempt/"vehicle_signal_history.jsonl")
    mapping = _rows(attempt/"video_frames.jsonl")
    trace = _rows(attempt/"trace.jsonl")
    if (len(history) != len(mapping) or len(trace) != len(mapping) or
            any(t.get("frame") != m.get("carla_frame") or
                t.get("time_s") != m.get("time_s") for t,m in zip(trace,mapping))):
        raise ValueError("Original trace/video frame join failed")
    counts = {name: _video_frames(attempt/(name+".mkv")) for name in CAMERAS}
    if any(count != len(mapping) for count in counts.values()):
        raise ValueError("Four source camera frame counts differ from original map")
    capture = json.loads((attempt/"capture/manifest.json").read_text())
    if (capture.get("case_id") != case_id or
            capture.get("acquisition") not in ("original_live_run","synthetic_fixture") or
            capture.get("extraction_confirmed") is not True or
            capture.get("frames") != len(mapping)):
        raise ValueError("Complete capture extraction certificate required")
    seal = json.loads((attempt/"capture-seal.json").read_text())
    provenance = seal.get("provenance_kind")
    if (provenance not in ("native","synthetic_fixture") or
            (provenance == "native" and capture["acquisition"] != "original_live_run") or
            (provenance == "synthetic_fixture" and
             (capture["acquisition"] != "synthetic_fixture" or
              seal.get("diagnostic_fixture") is not True)) or
            seal.get("frames") != len(mapping) or
            seal.get("restoration", {}).get("restored") is not True or
            seal.get("physical_acceptance_claimed") is not False or
            any(code != 0 for code in seal.get("encoder_exit_codes", {}).values())):
        raise ValueError("Capture seal and acquisition provenance disagree")
    sealed_sources = seal.get("sources", {})
    for name in REQUIRED:
        if name != "capture-seal.json" and sealed_sources.get(name) != _sha(attempt/name):
            raise ValueError("Sealed original source changed: " + name)
    return {"case_id": case_id, "config": cfg, "source_report": report,
            "history": history, "frame_map": mapping, "camera_frame_counts": counts,
            "provenance_kind":provenance,
            "source_hashes": {name: _sha(attempt/name) for name in REQUIRED}}


def finalize_saved(attempt, output):
    """Create a fresh saved result only after independent source checks pass."""
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    output_root = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
    repo = next((parent for parent in Path(__file__).resolve().parents
                 if (parent/"batch.json").is_file()), None)
    if (repo is None or not output_root or
            not Path(output_root).resolve().is_relative_to(repo/".runtime-work")):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    if (not attempt.is_relative_to(Path(output_root).resolve()) or
            not output.is_relative_to(Path(output_root).resolve()) or output.exists()):
        raise ValueError("Fresh ignored saved analysis output required")
    if (attempt/"result.json").exists() or (attempt/"channels").exists():
        raise ValueError("Retain prior finalization; choose a fresh attempt")
    proof = validate_sources(attempt)
    report = proof["source_report"]
    history = proof["history"]
    channels = {
        "ego_speed": ("m/s", lambda row: row["ego"]["speed_mps"]),
        "earlier_speed": ("m/s", lambda row: row["earlier"]["speed_mps"]),
        "occupant_speed": ("m/s", lambda row: row["occupant"]["speed_mps"]),
        "ego_stop_line_distance": ("m", lambda row: row["ego"]["front_to_stop_line_signed_m"]),
        "earlier_stop_line_distance": ("m", lambda row: row["earlier"]["front_to_stop_line_signed_m"]),
        "occupant_stop_line_distance": ("m", lambda row: row["occupant"]["front_to_stop_line_signed_m"]),
        "governing_signal_states": ("device states", lambda row: row["signal_states"]),
    }
    derived = {name: [value(row) for row in history]
               for name,(_,value) in channels.items()}
    from worker_exchange.native_output import physical_result, write_result

    evidence_root = attempt/"evidence"
    evidence_root.mkdir(exist_ok=True)
    for name in ("config.json", "trace.jsonl", "vehicle_signal_history.jsonl",
                 "video_frames.jsonl", "junction_context.json"):
        shutil.copyfile(attempt/name,evidence_root/name)
    shutil.copytree(attempt/"capture",evidence_root/"capture",dirs_exist_ok=True)
    channel_root = attempt/"channels"
    channel_root.mkdir()
    evidence = []
    for name,(unit,_) in channels.items():
        reference = "channels/"+name+".jsonl"
        with (attempt/reference).open("x") as stream:
            for row,value in zip(history,derived[name]):
                stream.write(json.dumps({"time_s":row["time_s"],
                    "original_frame":row["frame"],"value":value},allow_nan=False)+"\n")
        evidence.append({"name":name,"unit":unit,"reference":reference})
    evidence.append({"name":"junction_context","unit":"structured record",
                     "reference":"junction_context.json"})
    checksums = {"evidence/"+path.relative_to(evidence_root).as_posix():_sha(path)
                 for path in evidence_root.rglob("*") if path.is_file()}
    (attempt/"evidence-checksums.json").write_text(json.dumps(checksums,sort_keys=True)+"\n")
    result = {"case_id":proof["case_id"],
        "measured_values": {"first_full_halt":report["first_full_halt"],
                            "first_body_entry":report["first_body_entry"],
                            "earlier_stopped_before_ego":report["distinct_other_stopped_earlier_observed"],
                            "occupant_inside_at_ego_entry":report["distinct_occupant_inside_at_ego_entry_observed"]},
        "target_checks":[{"target":"exact_branch_original_frame_observations",
                          "requested":True,"measured":True,"matched":True,
                          "method":"source-hashed three-body and all-head frame joins",
                          "tolerance":0,"physical_cause_confirmed":False,
                          "cause_evidence":list(report["sources"])}],
        "setup_confirmed":False,"behavior_attempted":False,
        "maneuver_completed":False,"termination_reason":"Saved source assessment pending",
        "physical_failure_flags":["Native signal visibility and legal judgments require original review"],
        "trace_reference":"trace.jsonl",
        "video_references":[name+".mkv" for name in CAMERAS],
        "video_frame_map_reference":"video_frames.jsonl",
        "recording_description":proof["config"].get("recording_description",{}),
        "recording_evidence":evidence,"source_evidence_hashes":report["sources"],
        "capture_evidence_sha256":_sha(attempt/"capture/evidence.jsonl"),
        "realized_observables":{}}
    result = physical_result(attempt,result)
    write_result(attempt,result)
    analysis = {"format":"worker-analysis-report","case_id":proof["case_id"],
                "source_report":report,"source_hashes":proof["source_hashes"],
                "measurements":{key:{"method":method.__name__,
                    "value":method(report,json.loads((attempt/"junction_context.json").read_text())),
                    "sources":{name:report["sources"][name]
                               for name in MEASUREMENT_INPUTS}}
                    for key,method in MEASUREMENT_METHODS.items()},
                "camera_frame_counts":proof["camera_frame_counts"],
                "physical_checks":result["physical_checks"],
                "realized_observables":result["realized_observables"],
                "provenance_kind":result["provenance_kind"],
                "diagnostic_fixture":result["diagnostic_fixture"],
                "limitations":["Physical signal status, occlusion, motion and legal judgments unresolved"],
                "legal_verdict_asserted":False,"analysis_complete":True}
    output.write_text(json.dumps(analysis,indent=2,allow_nan=False)+"\n")
    return analysis


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize_saved(args.attempt, args.output)


if __name__ == "__main__":
    main()

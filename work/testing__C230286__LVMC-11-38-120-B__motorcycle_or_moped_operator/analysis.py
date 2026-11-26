"""Saved-only source-bound lamp measurements and Native result finalization."""

import argparse
import hashlib
import json
from pathlib import Path

from lamp_observations import measure
from source_packet import SOURCE_NAMES, verify


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required source: " + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def analyze(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, "config.json").read_text(encoding="utf-8"))
    construction = json.loads(required(root, "construction.json").read_text(encoding="utf-8"))
    case_id = config["selected_case_id"]
    if construction["case_id"] != case_id:
        raise ValueError("selected lamp construction identity differs")
    diagnostic = required(root, "fixture-provenance.json").is_file() if (root / "fixture-provenance.json").exists() else False
    source_dir = root / "original-lamp-source"
    packet_path = required(root, "original-lamp-source/source-packet.json")
    packet = verify(packet_path, diagnostic_fixture=diagnostic)
    if packet["case_id"] != case_id:
        raise ValueError("source packet selected another exact lamp case")
    context_path = required(root, "original-lamp-source/context.json")
    trace_path = required(root, "original-lamp-source/lamp-trace.jsonl")
    receipt_path = required(root, "original-lamp-source/source-receipt.json")
    measured = measure(case_id, context_path, trace_path, receipt_path,
                       diagnostic_fixture=diagnostic)
    native_trace = rows(required(root, "trace.jsonl"))
    video_map = rows(required(root, "video_frames.jsonl"))
    expected = 9 if diagnostic else config["capture_frames"]
    if len(native_trace) != expected or len(video_map) != expected or \
            len(measured["observations"]) != expected:
        raise ValueError("original lamp, Native trace and four-view frame count mismatch")
    for index, (lamp, native, video) in enumerate(zip(measured["observations"], native_trace, video_map)):
        if (lamp["carla_frame"] != native["frame"] or
                video["native_frame"] != native["frame"] or
                video["video_frame"] != index):
            raise ValueError("original lamp/Native/video frame join differs")
    context = json.loads(context_path.read_text(encoding="utf-8"))
    refs = context["source_refs"]
    source_hashes = {"original-lamp-source/" + name: sha(required(root, "original-lamp-source/" + name))
                     for name in ("source-packet.json", "context.json", "lamp-trace.jsonl",
                                  "source-receipt.json")}
    source_hashes.update({"original-lamp-source/" + ref["path"]: ref["sha256"]
                          for ref in refs.values()})
    source_hashes["trace.jsonl"] = sha(root / "trace.jsonl")
    source_hashes["video_frames.jsonl"] = sha(root / "video_frames.jsonl")
    names = {
        "covered_vehicle_context": ["source-packet.json", "context.json", refs["vehicle_coverage"]["path"]],
        "headlamp_white_forward_capability": ["context.json", refs["headlamp_photometry"]["path"]],
        "taillamp_red_rear_capability": ["context.json", refs["tail_lamp_photometry"]["path"]],
        "astronomical_motion_interval": ["context.json", "lamp-trace.jsonl",
                                         refs["astronomical_times"]["path"], "trace.jsonl"],
        "forward_discernibility_condition": ["context.json", refs["light_atmosphere"]["path"],
                                               refs["discernibility_protocol"]["path"]],
        "original_lamp_burning_duty": ["lamp-trace.jsonl", "source-receipt.json", "trace.jsonl",
                                       "video_frames.jsonl"],
    }
    values = {
        "covered_vehicle_context": {"source_sha256": refs["vehicle_coverage"]["sha256"],
                                    "request": config["case"]["coverage_request"],
                                    "covered_status_judgment": "unresolved"},
        "headlamp_white_forward_capability": measured["calibrated_headlamp"],
        "taillamp_red_rear_capability": measured["calibrated_tail_lamp"],
        "astronomical_motion_interval": {"offsets_minutes": measured["astronomical_offsets_minutes"],
                                          "moving_frames": measured["lamp_motion_summary"]["moving_frames"]},
        "forward_discernibility_condition": {
            "observed_discernibility_ft": measured["observed_discernibility_ft"],
            "visibility_judgment": measured["visibility_judgment"]},
        "original_lamp_burning_duty": measured["lamp_motion_summary"],
    }
    measurements = {}
    for key, value in values.items():
        inputs = {("" if name in ("trace.jsonl", "video_frames.jsonl") else
                   "original-lamp-source/") + name: source_hashes[("" if name in
                   ("trace.jsonl", "video_frames.jsonl") else "original-lamp-source/") + name]
                  for name in names[key]}
        measurements[key] = {"method": "analyze", "value": value, "sources": inputs}
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": measurements, "diagnostic_fixture": diagnostic,
              "legal_verdict_claimed": False,
              "limitations": ["Original calibrated photometry and Native camera source review remain required."]}
    channels = root / "channels"
    channels.mkdir(exist_ok=False)
    evidence = []
    source_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    for channel in construction["recording_description"]["channels"]:
        name = channel["name"]
        target = channels / (name + ".jsonl")
        with target.open("x", encoding="utf-8") as stream:
            for index, native in enumerate(native_trace):
                stream.write(json.dumps({"time_s": native["time_s"],
                                         "value": {"source_case": case_id,
                                                   "original_frame": native["frame"],
                                                   "lamp_observation": measured["observations"][index],
                                                   "context_source_sha256": sha(context_path)}},
                                        sort_keys=True) + "\n")
        evidence.append({"name": name, "unit": channel["unit"],
                         "reference": str(target.relative_to(root))})
    for context_input in construction["recording_description"]["context_inputs"]:
        name = context_input["name"]
        ref = source_packet["source_refs"][name]
        target = channels / (name + ".json")
        target.write_text(json.dumps({name: {"source_sha256": ref["sha256"],
                                             "reviewed_by": ref["reviewed_by"]}},
                                     sort_keys=True) + "\n", encoding="utf-8")
        evidence.append({"name": name, "unit": context_input["unit"],
                         "reference": str(target.relative_to(root))})
    result = {"case_id": case_id,
              "measured_values": {"lamp_motion": measured["lamp_motion_summary"],
                                  "headlamp": measured["calibrated_headlamp"],
                                  "taillamp": measured["calibrated_tail_lamp"],
                                  "discernibility_ft": measured["observed_discernibility_ft"],
                                  "astronomical_offsets_minutes": measured["astronomical_offsets_minutes"]},
              "target_checks": [{"target": "source-bound lamp and motion observations",
                                 "requested": config["case"],
                                 "measured": measured["lamp_motion_summary"],
                                 "method": "lamp_observations.measure",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": source_hashes}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False,
              "termination_reason": "Original lamp capability and physical completion review pending",
              "physical_failure_flags": [], "trace_reference": "trace.jsonl",
              "video_references": [name + ".mkv" for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": evidence, "realized_observables": {},
              "legal_judgment": None, "physical_acceptance_claimed": False}
    required(root, "capture/manifest.json")
    (root / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                                      encoding="utf-8")
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)["case_id"])


if __name__ == "__main__":
    main()

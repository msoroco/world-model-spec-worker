"""Saved-only source-bound signal finalizer; legal form remains unresolved."""

import argparse
import hashlib
import json
from pathlib import Path

from signal_measurements import measure

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def measure_case(case_id, attempt, diagnostic_mode):
    return measure(case_id=case_id,
                   context_path=attempt / "signal-context.json",
                   trace_path=attempt / "signal-readback.jsonl",
                   receipt_path=attempt / "signal-receipt.json",
                   allow_diagnostic=diagnostic_mode)


def original(attempt, case_id):
    manifest_path = attempt / "original-sources.json"
    if not manifest_path.is_file():
        raise ValueError("sealed original source manifest missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("source_kind") != "original_native_capture" or not manifest.get("accepted_original_source"):
        raise ValueError("original Native provenance missing")
    if manifest.get("case_id") != case_id or manifest.get("frame_count") != 900 or \
            manifest.get("camera_frame_counts") != {name: 900 for name in VIEWS}:
        raise ValueError("original exact case or four-camera frame count differs")
    names = ("config.json", "signal-context.json", "signal-receipt.json",
             "signal-readback.jsonl", "trace.jsonl", "video_frames.jsonl") + tuple(
                 name + ".mkv" for name in VIEWS)
    for name in names:
        path = (attempt / name).resolve()
        if not path.is_relative_to(attempt) or not path.is_file() or path.is_symlink() or \
                manifest.get("files", {}).get(name, {}).get("sha256") != sha(path):
            raise ValueError("original source bytes missing or changed: " + name)
    return manifest


def diagnostic(attempt, case_id):
    note_path = attempt / "diagnostic-source-note.json"
    receipt_path = attempt / "signal-receipt.json"
    if not note_path.is_file() or not receipt_path.is_file():
        raise ValueError("diagnostic source note and receipt missing")
    note = json.loads(note_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    if note.get("scope") != "software_fixture_only" or \
            note.get("case_id") != case_id or \
            receipt.get("case_id") != case_id or \
            receipt.get("diagnostic_fixture") is not True:
        raise ValueError("diagnostic fixture provenance differs")
    names = ("config.json", "signal-context.json", "signal-receipt.json",
             "signal-readback.jsonl", "trace.jsonl", "video_frames.jsonl") + tuple(
                 name + ".mkv" for name in VIEWS)
    files = {}
    for name in names:
        path = attempt / name
        if not path.is_file():
            raise ValueError("Missing required source: " + name)
        files[name] = {"sha256": sha(path)}
    return {"source_kind": "diagnostic_software_fixture", "files": files,
            "reviewed_scene_packet_sha256": "diagnostic_not_original"}


def analyze(attempt, output):
    attempt = Path(attempt).resolve()
    config = json.loads((attempt / "config.json").read_text())
    case_id = config["selected_case_id"]
    diagnostic_mode = (attempt / "diagnostic-source-note.json").exists()
    manifest = diagnostic(attempt, case_id) if diagnostic_mode else original(attempt, case_id)
    rows = read_rows(attempt / "signal-readback.jsonl")
    trace = read_rows(attempt / "trace.jsonl")
    mapping = read_rows(attempt / "video_frames.jsonl")
    expected_frames = 9 if diagnostic_mode else 900
    if len(rows) != len(trace) or len(trace) != len(mapping) or len(rows) != expected_frames:
        raise ValueError("original frame/time stream lengths differ")
    for index, (row, native, video) in enumerate(zip(rows, trace, mapping)):
        if native.get("frame") != row.get("frame") or \
                video.get("carla_frame") != row.get("frame") or \
                video.get("video_frame") != index or \
                abs(video.get("time_s", -1) - row.get("time_s", -2)) > 1e-4 or \
                abs(native.get("time_s", -1) - row.get("time_s", -2)) > 1e-4:
            raise ValueError("original trace/video/signal frame join differs")
    observation = measure_case(case_id, attempt, diagnostic_mode)
    channels = attempt / "channels"
    channels.mkdir(exist_ok=False)
    values = {
        "roadway_occupancy": lambda row: row["on_roadway"],
        "right_arm_pose": lambda row: row["right_arm"],
        "right_turn_heading": lambda row: row["operator_heading"],
        "camera_frame_identity": lambda row: row["frame"],
    }
    evidence = []
    for channel in config["case"]["recording_description"]["channels"]:
        name = channel["name"]
        if name not in values:
            raise ValueError("unimplemented original signal channel: " + name)
        relative = "channels/" + name + ".jsonl"
        (attempt / relative).write_text("".join(json.dumps({
            "time_s": row["time_s"], "value": values[name](row)}, sort_keys=True) + "\n"
            for row in observation["observations"]), encoding="utf-8")
        evidence.append({"name": name, "unit": channel["unit"], "reference": relative})
    context_relative = "channels/reviewed_signal_scene.json"
    (attempt / context_relative).write_text(json.dumps({"reviewed_signal_scene": {
        "source_sha256": sha(attempt / "signal-context.json"),
        "reviewed_scene_packet_sha256": manifest["reviewed_scene_packet_sha256"],
        "legal_reference_review": "pending"}}, sort_keys=True) + "\n")
    evidence.append({"name": "reviewed_signal_scene", "unit": "source",
                     "reference": context_relative})
    native = {
        "case_id": case_id,
        "measured_values": {"right_arm_roadway_turn": {
            "frame_count": expected_frames, "roadway_frames": len(observation["roadway_frames"]),
            "right_arm_first": observation["observations"][0]["right_arm"],
            "right_arm_last": observation["observations"][-1]["right_arm"]}},
        "target_checks": [{"target": "sourced right-turn roadway rider-arm event",
                           "requested": config["case"]["requested_signal_posture"],
                           "measured": observation["observations"][0]["right_arm"],
                           "method": "source-bound original joint readback",
                           "tolerance": None, "matched": False,
                           "physical_cause_confirmed": False,
                           "cause_evidence": ["signal-context.json", "signal-readback.jsonl"]}],
        "setup_confirmed": False, "behavior_attempted": False,
        "maneuver_completed": False,
        "termination_reason": "independent physical and original-pixel review pending",
        "physical_failure_flags": [], "trace_reference": "trace.jsonl",
        "video_references": [name + ".mkv" for name in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": config["case"]["recording_description"],
        "recording_evidence": evidence, "realized_observables": {},
        "physical_acceptance_claimed": False,
        "diagnostic_fixture": diagnostic_mode,
        "signal_form_judgment": "unresolved",
    }
    from worker_exchange.native_output import write_result
    write_result(attempt, native)
    report = {"format": "worker-analysis-report", "case_id": case_id,
              "measurements": {"right_arm_roadway_turn": {
                  "method": "measure_case",
                  "value": observation,
                  "sources": {name: manifest["files"][name]["sha256"] for name in
                              ("signal-context.json", "signal-readback.jsonl",
                               "signal-receipt.json")}}},
              "limitations": ["Actual arm pixels and legal signal form remain independent review."]}
    Path(output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(analyze(args.attempt, args.output), sort_keys=True))


if __name__ == "__main__":
    main()

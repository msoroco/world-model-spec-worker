"""Saved-only C104538 mounted-bicycle diagnostic; never a legal finding."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def video_frames(path):
    if not path.is_file():
        raise ValueError("Missing required source: "+path.name)
    result = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError("Source camera decode failed: "+path.name)
    return int(result.stdout.strip())


def finalize(attempt, output):
    root, target = Path(attempt), Path(output)
    if target.exists() or (root/"result.json").exists():
        raise ValueError("Retain prior saved result; use a fresh attempt")
    config = json.loads((root/"config.json").read_text())
    kind = config["case_suffix"]
    if kind not in ("mounted_obey", "mounted_turn") or config["rate_hz"]*config["duration_s"] != 480:
        raise ValueError("Exact mounted case/timebase differs")
    native = rows(root/"native_samples.jsonl")
    mapping = rows(root/"video_frames.jsonl")
    rider = rows(root/"rider_native_samples.jsonl")
    trace = rows(root/"trace.jsonl")
    evidence = rows(root/"capture/evidence.jsonl")
    body = rows(root/"body_history.jsonl")
    if any(len(data) != 480 for data in (native, mapping, rider, trace, evidence, body)):
        raise ValueError("Original-style 480-frame join incomplete")
    manifest_path = root/"rider-source-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("Missing required source: rider-source-manifest.json")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("source_kind") != "synthetic_native_shaped_diagnostic" or manifest.get("case_suffix") != kind:
        raise ValueError("Unreviewed source kind or case differs")
    if manifest.get("rider_samples_sha256") != sha(root/"rider_native_samples.jsonl"):
        raise ValueError("Rider source hash differs")
    if manifest.get("sign_sha256") != sha(root/"authored-sign.json"):
        raise ValueError("Sign packet hash differs")
    sign = json.loads((root/"authored-sign.json").read_text())
    if (sign.get("code") != "no_u_turn" or sign.get("station_m") != 72.0 or
            sign.get("authorization_proven") is not False):
        raise ValueError("Synthetic sign scope differs")
    turn_frames = mounted_turn_frames = 0
    for i, (n, m, r, t, e, b) in enumerate(zip(native, mapping, rider, trace, evidence, body)):
        frame, time = n["native_frame"], n["time_s"]
        if (r["frame"] != i or r["time_s"] != time or r["actor_id"] != "rider-1" or
            r["machine_class"] != "bicycle" or r["sign_id"] != sign["id"] or
            r["road_id"] != sign["governs_road"] or r["approach_lane_id"] != sign["governs_lane"]):
            raise ValueError("Rider/sign/frame source join differs")
        if (m["video_frame"] != i or m["native_frame"] != frame or m["carla_frame"] != frame or
            m["time_s"] != time or t["frame"] != frame or e["original_frame"] != frame or
            b["frame"] != frame):
            raise ValueError("Native/source frame identity differs")
        if n["native_center_xy_m"] != [r["x_m"], r["y_m"]]:
            raise ValueError("Rider/Native position differs")
        if {tuple(p) for p in n["native_body_xy_m"]} != {tuple(p[:2]) for p in b["body_vertices_m"]}:
            raise ValueError("Native/body history differs")
        if r["walking_machine"] is r["mounted"]:
            raise ValueError("Rider posture contradicts machine state")
        turn_frames += int(r["u_turn_active"])
        mounted_turn_frames += int(r["u_turn_active"] and r["mounted"])
    expected = kind == "mounted_turn"
    measured = mounted_turn_frames > 0
    if measured != expected or (kind == "mounted_obey" and turn_frames):
        raise ValueError("Controlled mounted-turn source differs")
    capture = json.loads((root/"capture/manifest.json").read_text())
    if capture.get("frames") != 480 or not capture.get("extraction_confirmed"):
        raise ValueError("Capture extraction incomplete")
    names = ("overview", "approach", "sign_reference", "driver_reference")
    videos = {name+".mkv": video_frames(root/(name+".mkv")) for name in names}
    if any(value != 480 for value in videos.values()):
        raise ValueError("Source camera frame count differs")
    description = config["recording_description"]
    recording = []
    for channel in description["channels"]:
        reference = "channels/"+channel["name"]+".jsonl"
        if not (root/reference).is_file():
            raise ValueError("Missing required source: "+reference)
        recording.append({"name": channel["name"], "unit": channel["unit"], "reference": reference})
    if not (root/"context.json").is_file():
        raise ValueError("Missing required source: context.json")
    for context in description["context_inputs"]:
        recording.append({"name": context["name"], "unit": context["unit"], "reference": "context.json"})
    result = {"case_id": config["case_id"],
        "measured_values": {"mounted_turn_frames": mounted_turn_frames, "turn_frames": turn_frames,
                            "sign_authorization_proven": False},
        "target_checks": [{"target": "mounted bicycle turns through authored no-U-turn region",
            "requested": expected, "measured": measured,
            "method": "saved synthetic rider/sign/frame joins", "tolerance": "exact boolean source check",
            "matched": expected == measured, "physical_cause_confirmed": False,
            "cause_evidence": ["rider_native_samples.jsonl", "authored-sign.json"]}],
        "setup_confirmed": False, "behavior_attempted": True, "maneuver_completed": True,
        "termination_reason": "full synthetic source duration retained",
        "physical_failure_flags": ["original_rider_posture_sign_authorization_and_pixels_unverified"],
        "trace_reference": "trace.jsonl", "video_references": list(videos),
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description, "recording_evidence": recording,
        "realized_observables": {}, "provenance_kind": "native", "accepted": False,
        "legal_verdict_claimed": False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {"format": "c104538-lvmc-synthetic-saved-mounted-diagnostic-v1",
        "case_id": config["case_id"], "candidate_id": config["candidate_id"],
        "source_kind": manifest["source_kind"], "frames": 480, "video_frames": videos,
        "turn_frames": turn_frames, "mounted_turn_frames": mounted_turn_frames,
        "source_hashes": {name: sha(root/name) for name in
            ("rider_native_samples.jsonl", "authored-sign.json", "native_samples.jsonl",
             "video_frames.jsonl", "capture/manifest.json")},
        "sign_authorization_proven": False, "original_native_capture_executed": False,
        "legal_verdict_claimed": False, "accepted": False}
    target.write_text(json.dumps(report, indent=2, allow_nan=False)+"\n")
    (root/"result.json").write_text(json.dumps(result, indent=2, allow_nan=False)+"\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))

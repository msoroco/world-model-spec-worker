"""Independent CPU audit of the observed primary's saved source and result.

Synthetic diagnostics prove the saved software path, never human perception,
physical camera quality, right-pass permission, or legal compliance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

CASE_ID = "heldout__C179789__NRS-484B-207-2__motor_vehicle_driver__observed_gives_way_holds_speed"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("overtaken_source.jsonl", "video_frames.jsonl", "trace.jsonl")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("Missing original delivery source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path, count):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
         "-show_entries", "stream=nb_read_frames", "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True, check=True)
    if int(probe.stdout.strip()) != count:
        raise ValueError("Original camera frame count differs: " + path.name)
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "null", "-"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True)
    return {"sha256": digest(path), "decoded_frames": count}


def audit(attempt, saved_receipt, analysis_override=None):
    attempt = Path(attempt)
    saved = json.loads(Path(saved_receipt).read_text())
    if (saved.get("case_id") != CASE_ID or saved.get("passed") is not True or
            saved.get("originals_preserved") is not True or saved.get("missing_evidence") is not False):
        raise ValueError("Saved processing identity or source status differs")
    stage = Path(analysis_override or saved["analysis_directory"])
    original_hashes = saved["original_source_hashes"]
    for name in SOURCES + tuple(camera + ".mkv" for camera in CAMERAS):
        if original_hashes.get(name) != digest(required(attempt, name)):
            raise ValueError("Original attempt source hash differs: " + name)
        if original_hashes[name] != digest(required(stage, name)):
            raise ValueError("Saved analysis source hash differs: " + name)
    body, mapping, trace = (rows(required(stage, name)) for name in SOURCES)
    if not body or len(body) != len(mapping) or len(body) != len(trace):
        raise ValueError("Saved delivery frame count differs")
    notice = completion = None
    samples = []
    first_ids = body[0].get("subject_id"), body[0].get("overtaker_id")
    for index, (b, m, t) in enumerate(zip(body, mapping, trace)):
        frame = b.get("frame")
        if ((b.get("subject_id"), b.get("overtaker_id")) != first_ids or
                m.get("video_frame") != index or m.get("carla_frame") != frame or
                t.get("frame") != frame or b.get("time_s") != m.get("time_s") or
                b.get("time_s") != t.get("time_s")):
            raise ValueError("Saved delivery identity/frame join differs")
        tangent = b["road_tangent_xy"]
        pose, waypoint = b["subject_pose_xy"], b["road_waypoint_xy"]
        if any(not math.isfinite(float(v)) for v in tangent + pose + waypoint):
            raise ValueError("Saved delivery nonfinite road geometry")
        right = (pose[0]-waypoint[0])*tangent[1] - (pose[1]-waypoint[1])*tangent[0]
        subject_long = [sum(x*y for x, y in zip(corner, tangent)) for corner in b["subject_corners"]]
        overtaker_long = [sum(x*y for x, y in zip(corner, tangent)) for corner in b["overtaker_corners"]]
        complete = min(overtaker_long) > max(subject_long)
        if (abs(right-b["subject_right_offset_m"]) > 1e-6 or
                abs(t["speed_mps"]-b["subject_speed_mps"]) > 1e-5 or
                complete != b["body_pass_complete"]):
            raise ValueError("Saved delivery original motion readback differs")
        relation = b.get("visibility_relation")
        if relation is not None:
            rays = relation.get("rays", [])
            visible = any(ray.get("clear") is True and not ray.get("blockers") for ray in rays)
            if (not rays or visible != relation.get("visible") or
                    visible != b.get("notice_observed") or
                    str(relation.get("a")) != first_ids[0] or str(relation.get("b")) != first_ids[1]):
                raise ValueError("Saved delivery original visibility rays differ")
        elif b.get("notice_observed") is not None:
            raise ValueError("Saved delivery visibility notice lacks rays")
        if b.get("notice_observed") is True and notice is None:
            notice = index
        if notice is not None and index > notice and complete and completion is None:
            completion = index
        samples.append((frame, b["time_s"], right, t["speed_mps"]))
    if notice is None or completion is None or completion <= notice + 1:
        raise ValueError("Saved delivery notice/completion interval absent")
    interval = samples[notice+1:completion]
    expected = {"right_shift_m": max(s[2]-samples[notice][2] for s in interval),
                "speed_delta_mps": max(s[3]-samples[notice][3] for s in interval),
                "pass_complete_frame": samples[completion][0]}
    report = json.loads(required(stage, "analysis-report.json").read_text())
    result = json.loads(required(stage, "result.json").read_text())
    if (report.get("case_id") != CASE_ID or result.get("case_id") != CASE_ID or
            result.get("physical_acceptance_claimed") is not False or
            result.get("legal_acceptance_claimed") is not False):
        raise ValueError("Saved delivery analysis identity or acceptance differs")
    source_hashes = {name: original_hashes[name] for name in SOURCES}
    for name, value in expected.items():
        item = report.get("measurements", {}).get(name, {})
        if item.get("value") != value or item.get("sources") != source_hashes:
            raise ValueError("Saved delivery measurement differs: " + name)
    response = result.get("measured_values", {}).get("overtaken_response", {})
    if (response.get("max_right_shift_m") != expected["right_shift_m"] or
            response.get("max_precompletion_speed_delta_mps") != expected["speed_delta_mps"] or
            response.get("pass_complete_frame") != expected["pass_complete_frame"]):
        raise ValueError("Saved delivery result differs from original motion")
    evidence = {item["name"]: item for item in result.get("recording_evidence", [])}
    required_evidence = {"subject_right_offset_m", "subject_speed_mps",
                         "observed_notice_source_context", "audible_signal_source_context",
                         "full_body_pass_gap_m", "right_pass_permission_context"}
    if set(evidence) != required_evidence:
        raise ValueError("Saved delivery channel inventory differs")
    for name in required_evidence - {"subject_right_offset_m", "subject_speed_mps"}:
        path = required(stage, evidence[name]["reference"])
        if digest(path) != evidence[name]["sha256"]:
            raise ValueError("Saved semantic channel hash differs: " + name)
        if name == "right_pass_permission_context":
            context = json.loads(path.read_text())
            if context.get("right_pass_permission_context", {}).get("legal_conclusion") is not None:
                raise ValueError("Saved permission channel asserts a legal outcome")
        elif len(rows(path)) != len(body):
            raise ValueError("Saved semantic channel frame count differs: " + name)
    for name, values in (("subject_right_offset_m", [s[2] for s in samples]),
                         ("subject_speed_mps", [s[3] for s in samples])):
        path = required(stage, evidence[name]["reference"])
        if digest(path) != evidence[name]["sha256"] or [row["value"] for row in rows(path)] != values:
            raise ValueError("Saved delivery derived channel differs: " + name)
    cameras = {name: decode(required(stage, name+".mkv"), len(body)) for name in CAMERAS}
    fixture_marker = stage / "fixture-provenance.json"
    fixture_only = (json.loads(fixture_marker.read_text()).get("diagnostic_fixture") is True
                    if fixture_marker.is_file() else False)
    return {"format":"worker-overtaken-delivery-audit", "case_id":CASE_ID,
            "source_sha256":source_hashes, "frames":len(body), "measurements":expected,
            "four_camera_decode":cameras, "originals_preserved":True,
            "fixture_only":fixture_only,
            "physical_acceptance_claimed":False, "legal_acceptance_claimed":False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--saved-receipt", required=True)
    parser.add_argument("--analysis-override")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.saved_receipt, args.analysis_override), indent=2))


if __name__ == "__main__":
    main()

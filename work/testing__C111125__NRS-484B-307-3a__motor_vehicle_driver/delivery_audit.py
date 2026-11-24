"""Independent saved-source audit for exact dual-green delivery preparation.

Diagnostic fixtures exercise the source joins and media decoder. They never
establish the physical dual-aspect signal, lawful use, or right of way.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from dual_green import measure_original, read_source, require
from camera_audit import audit_cameras


PREFIX = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
SUFFIXES = {"dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late"}
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()) and path.is_file(),
            "Missing required source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def audit(attempt, case_id, *, diagnostic=False):
    root = Path(attempt).resolve()
    require(case_id.startswith(PREFIX) and case_id[len(PREFIX):] in SUFFIXES,
            "wrong exact delivery case")
    result_path = source(root, "result.json")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    require(result.get("case_id") == case_id, "Native result case mismatch")
    capture = json.loads(source(root, "capture/manifest.json").read_text())
    require(capture.get("case_id") == case_id, "capture case mismatch")
    require(bool(capture.get("diagnostic_fixture")) is diagnostic,
            "diagnostic/Native provenance mismatch")
    count = 5 if diagnostic else 900
    require(capture.get("frames") == count, "capture duration mismatch")
    site = json.loads(source(root, "site.json").read_text())
    event_path = source(root, "original-events.json")
    measured = measure_original(site, root, {"path": "original-events.json",
                                             "sha256": sha(event_path)})
    require(len(measured["records"]) == count, "original event history incomplete")
    handoff = json.loads(source(root, "original-source-handoff.json").read_text())
    require(handoff.get("case_id") == case_id and len(handoff.get("frames", [])) == count,
            "original packet inventory incomplete")
    event = json.loads(event_path.read_text())
    for observed, packet in zip(event, handoff["frames"]):
        require(packet.get("carla_frame") == observed.get("frame"),
                "original packet/event frame join failed")
        lamp_ref = packet.get("lamp")
        require(isinstance(lamp_ref, dict), "original lamp packet absent")
        lamp = json.loads(read_source(root, lamp_ref).read_text())
        require(lamp_ref["path"] == observed.get("aspect_observation_source") and
                lamp_ref["sha256"] == observed.get("aspect_observation_sha256"),
                "original lamp packet/event hash join failed")
        marker = lamp.get("original_observation")
        require(isinstance(marker, dict), "original lamp observation absent")
        read_source(root, marker)
        user_refs = packet.get("lawful_use", {})
        require(set(user_refs) == {str(u["id"]) for u in observed["other_users"]},
                "original lawful-use participant inventory differs")
        for user in observed["other_users"]:
            ref = user_refs[str(user["id"])]
            read_source(root, ref)
            require(ref["path"] == user["lawful_use_source"] and
                    ref["sha256"] == user["lawful_use_sha256"],
                    "original lawful-use source hash join failed")
    frame_map = rows(source(root, "video_frames.jsonl"))
    trace = rows(source(root, "trace.jsonl"))
    require(len(frame_map) == len(trace) == count, "original trace/frame map incomplete")
    for index, (mapping, sample, observed) in enumerate(zip(frame_map, trace, event)):
        require(mapping.get("video_frame") == index and
                mapping.get("carla_frame") == sample.get("frame") == observed.get("frame") and
                abs(float(mapping["time_s"]) - float(sample["time_s"])) < 1e-4,
                "original trace/frame map time join failed")
    references = result.get("video_references")
    require(references == [name + ".mkv" for name in VIEWS],
            "four original video references required")
    videos = {}
    for view, name in zip(VIEWS, references):
        path = source(root, name)
        probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                                "-count_frames", "-show_entries",
                                "stream=width,height,nb_read_frames,r_frame_rate",
                                "-of", "json", str(path)], capture_output=True, text=True)
        require(probe.returncode == 0, "original video probe failed: " + view)
        streams = json.loads(probe.stdout).get("streams", [])
        require(len(streams) == 1, "original video stream missing: " + view)
        stream = streams[0]
        require(int(stream.get("nb_read_frames", -1)) == count and
                stream.get("r_frame_rate") == "20/1", "original video frame/rate mismatch: " + view)
        if not diagnostic:
            require((stream["width"], stream["height"]) == SIZES[view],
                    "original video dimensions mismatch: " + view)
        decoded = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                                  "-map", "0:v:0", "-f", "null", "-"],
                                 capture_output=True, text=True)
        require(decoded.returncode == 0, "original video full decode failed: " + view)
        pixels = subprocess.run(["ffmpeg", "-v", "error", "-xerror", "-i", str(path),
                                 "-map", "0:v:0", "-frames:v", "1", "-f", "rawvideo",
                                 "-pix_fmt", "rgb24", "-"], capture_output=True)
        require(pixels.returncode == 0 and len(pixels.stdout) ==
                3 * int(stream["width"]) * int(stream["height"]),
                "original decoded pixel buffer missing: " + view)
        videos[view] = {"sha256": sha(path), "frames": count,
                        "width": stream["width"], "height": stream["height"]}
    if not diagnostic:
        seal = json.loads(source(root, "capture-seal.json").read_text())
        require(seal.get("format") == "worker-sealed-capture" and
                seal.get("diagnostic_fixture") is False and
                seal.get("restoration", {}).get("restored") is True and
                seal.get("frames") == 900, "Native capture seal incomplete")
        saved = json.loads(source(root, "saved-observation.json").read_text())
        require(saved.get("case_id") == case_id and saved.get("frame_count") == 900 and
                saved.get("diagnostic_only") is False, "production saved audit incomplete")
        audit_cameras(root, case_id)
    return {"format": "dual-green-saved-source-audit", "case_id": case_id,
            "diagnostic_fixture": diagnostic, "software_checks_passed": True,
            "checks": {"native_source": not diagnostic,
                       "all_participants": True, "time_join": True,
                       "full_video_decode": True, "actual_pixels": True,
                       "physical_completion": False},
            "frames": count, "result_sha256": sha(result_path),
            "event_sha256": sha(event_path),
            "handoff_sha256": sha(root / "original-source-handoff.json"),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "trace_sha256": sha(root / "trace.jsonl"), "videos": videos,
            "physical_acceptance_claimed": False,
            "permission_verdict": None, "right_of_way_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--negative-remove-handoff", action="store_true")
    args = parser.parse_args()
    if args.negative_remove_handoff:
        require(args.diagnostic_fixture, "negative source removal requires diagnostic fixture")
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            stripped = Path(temporary) / "attempt"
            shutil.copytree(args.attempt, stripped, copy_function=os.link)
            source(stripped, "original-source-handoff.json").unlink()
            audit(stripped, args.case, diagnostic=True)
        raise ValueError("missing-source negative test was accepted")
    report = audit(args.attempt, args.case, diagnostic=args.diagnostic_fixture)
    output = Path(args.output)
    require(not output.exists(), "retain prior independent source audit")
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("independent saved-source audit passed: " + args.case)


if __name__ == "__main__":
    main()

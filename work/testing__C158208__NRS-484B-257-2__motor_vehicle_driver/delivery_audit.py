"""Independent original-source audit for one exact signed-entrance delivery.

This does not decide proper sign erection, officer authority, immediate hazard,
or statutory compliance. Diagnostic fixtures exercise structure only.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess


PREFIX = "testing__C158208__NRS-484B-257-2__motor_vehicle_driver__"
KINDS = {"yield_other_inside", "yield_other_approaching", "yield_other_obligated",
         "yield_no_slow", "officer_control_exception"}
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SOURCES = ("intersection_context.json", "entry_history.jsonl", "video_frames.jsonl",
           "site_review.json", *(name + ".mkv" for name in CAMERAS))


def sha(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path, dimensions, count):
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
         "-show_entries", "stream=width,height,nb_read_frames", "-of", "json", str(path)],
        capture_output=True, text=True)
    if probe.returncode:
        raise ValueError("Original camera probe failed: " + path.name)
    streams = json.loads(probe.stdout).get("streams", [])
    if len(streams) != 1 or (streams[0].get("width"), streams[0].get("height")) != dimensions:
        raise ValueError("Original camera dimensions changed: " + path.name)
    if int(streams[0].get("nb_read_frames", -1)) != count:
        raise ValueError("Original camera frame count differs: " + path.name)
    full = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
                           "-map", "0:v:0", "-f", "null", "-"],
                          capture_output=True, text=True)
    if full.returncode or full.stderr.strip():
        raise ValueError("Full original camera decode failed: " + path.name)


def audit(attempt, case_id, *, diagnostic_fixture=False):
    root = Path(attempt)
    if case_id.removeprefix(PREFIX) not in KINDS or not case_id.startswith(PREFIX):
        raise ValueError("Wrong exact signed-entrance case")
    config = read(root / "config.json")
    if (config.get("selected_case_id") != case_id
            or (config.get("law_id"), config.get("cell_id"), config.get("actor"),
                config.get("rate_hz"), config.get("duration_s")) != (
                "NRS-484B-257-2", "C158208", "motor_vehicle_driver", 20, 30)):
        raise ValueError("Exact case or capture profile changed")
    report = read(root / "analysis-report.json")
    original = report.get("raw_observations", {})
    if (report.get("case_id") != case_id or report.get("legal_conclusion") != "unresolved"
            or report.get("analysis_complete") is not True):
        raise ValueError("Incomplete source-bound saved analysis")
    for name in SOURCES:
        if original.get("sources", {}).get(name) != sha(root / name):
            raise ValueError("Original analysis source changed: " + name)
    measurements = report.get("measurements")
    if not isinstance(measurements, dict) or len(measurements) != 6:
        raise ValueError("Six selected source-bound measurements required")
    for key, item in measurements.items():
        if not isinstance(item, dict) or not isinstance(item.get("sources"), dict) or not item["sources"]:
            raise ValueError("Measurement source binding missing: " + key)
        for name, expected in item["sources"].items():
            if expected != original.get("sources", {}).get(name) or expected != sha(root / name):
                raise ValueError("Measurement source changed: " + key + ":" + name)
    frames = rows(root / "video_frames.jsonl")
    history = rows(root / "entry_history.jsonl")
    if len(frames) != len(history) or len(frames) < 3:
        raise ValueError("Incomplete original actor/camera history")
    if not diagnostic_fixture and len(frames) != 600:
        raise ValueError("Native delivery requires complete 600-frame capture")
    previous = None
    for index, (frame, actor) in enumerate(zip(frames, history)):
        time = frame.get("time_s")
        if (frame.get("video_frame") != index or type(frame.get("carla_frame")) is not int
                or type(time) not in (int, float) or not math.isfinite(time)
                or actor.get("frame") != frame["carla_frame"] or actor.get("time_s") != time
                or frame.get("camera_frame_ids") != {name: frame["carla_frame"] for name in CAMERAS}
                or len(actor.get("ego_body_vertices_xy_m", [])) < 4
                or len(actor.get("other_body_vertices_xy_m", [])) < 4):
            raise ValueError("Original four-camera/participant frame join failed")
        if previous is not None and (frame["carla_frame"] != previous[0] + 1
                                     or abs(time - previous[1] - .05) > 1e-3):
            raise ValueError("Original frame sequence is not continuous 20 Hz")
        previous = frame["carla_frame"], time
    context = read(root / "intersection_context.json")
    review = read(root / "site_review.json")
    if (context.get("case_id") != case_id or context.get("non_through_highway") is not True
            or context.get("ego_entrance_device") != "yield"
            or review.get("method") != "original_source_camera_frame_review"
            or review.get("intersection_context_sha256") != sha(root / "intersection_context.json")
            or review.get("native_yield_sign_id") != context.get("native_yield_sign_id")
            or review.get("reviewed_carla_frames") != [row["carla_frame"] for row in frames]
            or review.get("reviewed_frame_count") != len(frames)
            or review.get("camera_sha256") != {name: sha(root / (name + ".mkv"))
                                                for name in CAMERAS}
            or type(review.get("marked_stop_line_observed")) is not bool
            or type(review.get("near_crosswalk_observed")) is not bool):
        raise ValueError("Original signed-entrance site review is incomplete or stale")
    if not diagnostic_fixture and (review.get("sign_face_observed") != "yield"
                                   or not review.get("reviewer")
                                   or str(review["reviewer"]).startswith("CPU diagnostic")):
        raise ValueError("Independent original-camera sign review required")
    if case_id.endswith("__officer_control_exception"):
        officer = read(root / "officer_review.json")
        if (original["sources"].get("officer_review.json") != sha(root / "officer_review.json")
                or officer.get("intersection_context_sha256") != sha(root / "intersection_context.json")
                or officer.get("control_observed_at_entry") is not True
                or officer.get("reviewed_carla_frames") != [row["carla_frame"] for row in frames]
                or officer.get("camera_sha256") != {name: sha(root / (name + ".mkv"))
                                                    for name in CAMERAS}
                or officer.get("authority_judgment") != "unresolved"):
            raise ValueError("Original officer-control source is incomplete or stale")
        if not diagnostic_fixture:
            candidate = read(root / "officer-candidate.json")
            if (candidate.get("format") != "worker-officer-candidate-construction"
                    or candidate.get("blueprint_id") != "walker.pedestrian.0001"
                    or type(candidate.get("actor_id")) is not int
                    or candidate["actor_id"] != officer.get("officer_actor_id")
                    or officer.get("officer_candidate_sha256") != sha(root / "officer-candidate.json")):
                raise ValueError("Original officer candidate and review actor differ")
    if not diagnostic_fixture:
        sealed = read(root / "result.json")
        if (sealed.get("case_id") != case_id or sealed.get("provenance_kind") != "native"
                or sealed.get("setup_confirmed") is not True
                or sealed.get("behavior_attempted") is not True
                or sealed.get("maneuver_completed") is not True
                or any(sealed.get("physical_checks", {}).get(name, {}).get("status") != "met"
                       for name in ("setup", "target", "maneuver"))):
            raise ValueError("Sealed Native physical completion is not established")
    for name, dimensions in CAMERAS.items():
        decode(root / (name + ".mkv"), dimensions, len(frames))
    return {"format": "worker-c158208-2-independent-source-audit",
            "case_id": case_id, "original_frames": len(frames),
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "actor_history_sha256": sha(root / "entry_history.jsonl"),
            "analysis_sha256": sha(root / "analysis-report.json"),
            "source_cameras": {name: sha(root / (name + ".mkv")) for name in CAMERAS},
            "software_audit_passed": True, "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case,
                           diagnostic_fixture=args.diagnostic_fixture), sort_keys=True))


if __name__ == "__main__":
    main()

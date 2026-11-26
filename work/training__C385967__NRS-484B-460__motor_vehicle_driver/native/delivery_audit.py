"""Independent original source, joined-frame, reviewed-pixel delivery audit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from saved_angle import CASES as PARK_CASES, measure as measure_park, read_json, read_rows, sha
from saved_angle_activity import CASES as ACTIVITY_CASES, measure as measure_activity

CASES = PARK_CASES | ACTIVITY_CASES


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")
SOURCES = ("native_samples.jsonl", "body_history.jsonl", "video_frames.jsonl",
           "official_device.json", "road_geometry.json", "parking_context.json",
           "trace.jsonl", "capture/evidence.jsonl", "capture/manifest.json")


def require(value, message):
    if not value:
        raise ValueError(message)


def video(path):
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-count_frames", "-show_entries", "stream=nb_read_frames,width,height",
        "-of", "json", str(path)], capture_output=True, text=True, check=True,
        timeout=120)
    stream = json.loads(result.stdout)["streams"][0]
    require(int(stream["nb_read_frames"]) == 600, "Full source video decode differs")
    return int(stream["width"]), int(stream["height"])


def check_review(review, case, hashes, dimensions, source_kind):
    require(review.get("format") == "c385967-nrs460-independent-review-v1" and
        review.get("case_id") == case and review.get("source_kind") == source_kind and
        review.get("legal_verdict") is None, "Independent review identity differs")
    for name, digest in hashes.items():
        require(review.get("source_hashes", {}).get(name) == digest,
                "Independent review source stale: " + name)
    require(set(CHECKS) <= set(review.get("checks", [])),
            "Independent delivery checks missing")
    for key in ("physical_completion", "official_device_pixels_reviewed",
                "governed_highway_space_reviewed", "original_curb_pixels_reviewed",
                "original_body_containment_reviewed", "at_rest_activity_reviewed",
                "parked_heading_reviewed"):
        require(review.get(key) is True, "Original device, curb, body or activity review incomplete")
    if "__stop_condition_" in case or "__stand_condition_" in case:
        require(review.get("source_action_reviewed") is True,
                "Original stop or stand action review incomplete")
    boxes = review.get("pixel_boxes", [])
    require({"vehicle", "angle_device", "curb", "parking_space"} <=
            {box.get("claim") for box in boxes}, "Original reviewed pixel claims missing")
    for box in boxes:
        name, rect = box.get("source"), box.get("rect_xywh")
        require(name in CAMERAS and type(box.get("frame")) is int and
            0 <= box["frame"] < 600 and isinstance(rect, list) and len(rect) == 4 and
            all(type(value) is int and value >= 0 for value in rect) and
            rect[2] > 0 and rect[3] > 0, "Reviewed pixel box invalid")
        width, height = dimensions[name]
        require(rect[0] + rect[2] <= width and rect[1] + rect[3] <= height,
                "Reviewed pixel box exceeds source video")


def audit(case, attempt, review_path):
    attempt = Path(attempt).resolve()
    require(case in CASES, "Exact selected case differs")
    config = read_json(attempt / "config.json")
    require(config.get("case_id") == case, "Exact selected case differs")
    geometry = read_json(attempt / "road_geometry.json")
    require(geometry.get("provenance") == "original_native_capture",
            "Original Native road source required")
    hashes = {}
    for name in (*SOURCES, *(camera + ".mkv" for camera in CAMERAS)):
        path = attempt / name
        require(path.is_file(), "Missing original source: " + name)
        hashes[name] = sha(path)
    manifest = read_json(attempt / "capture/manifest.json")
    require(manifest.get("synthetic_diagnostic") is not True and
            manifest.get("frames") == 600,
            "Synthetic diagnostic cannot be original delivery")
    outcome = (measure_activity if "__stop_condition_" in case or
               "__stand_condition_" in case else measure_park)(attempt, case)
    samples, frames, trace = (read_rows(attempt / name) for name in
        ("native_samples.jsonl", "video_frames.jsonl", "trace.jsonl"))
    require(len(trace) == 600, "Original 600-frame trace absent")
    for i, (sample, frame, motion) in enumerate(zip(samples, frames, trace)):
        require(frame["video_frame"] == i and
            frame["carla_frame"] == sample["native_frame"] == motion["frame"] and
            abs(frame["time_s"] - sample["time_s"]) < .001 and
            abs(motion["time_s"] - sample["time_s"]) < .001,
            "Original Native/time join differs")
    dimensions = {name: video(attempt / (name + ".mkv")) for name in CAMERAS}
    review_path = Path(review_path)
    check_review(read_json(review_path), case, hashes, dimensions, "original_native")
    return {"format": "worker-delivery-audit", "case_id": case,
            "checks": list(CHECKS), "passed": True,
            "source_hashes": hashes, "review_sha256": sha(review_path),
            "measurement": outcome,
            "physical_acceptance_claimed_by_worker": False,
            "legal_verdict": None}


def selftest(case, fixture, negative):
    require(case in CASES, "Exact selected case differs")
    fixture = Path(fixture).resolve()
    hashes = {name: sha(fixture / name) for name in
        (*SOURCES, *(camera + ".mkv" for camera in CAMERAS))}
    dimensions = {name: video(fixture / (name + ".mkv")) for name in CAMERAS}
    review = {"format": "c385967-nrs460-independent-review-v1", "case_id": case,
        "source_kind": "synthetic_cpu_mechanics", "legal_verdict": None,
        "source_hashes": hashes, "checks": list(CHECKS),
        "physical_completion": True, "official_device_pixels_reviewed": True,
        "governed_highway_space_reviewed": True, "original_curb_pixels_reviewed": True,
        "original_body_containment_reviewed": True, "at_rest_activity_reviewed": True,
        "parked_heading_reviewed": True, "source_action_reviewed": True,
        "pixel_boxes": [{"claim": claim, "source": CAMERAS[i],
            "frame": 100+i, "rect_xywh": [0, 0, 4, 4]}
            for i, claim in enumerate(("vehicle", "angle_device", "curb", "parking_space"))]}
    if negative:
        review["pixel_boxes"][0]["rect_xywh"][0] = dimensions["overview"][0]
    check_review(review, case, hashes, dimensions, "synthetic_cpu_mechanics")
    require(not negative, "Negative review was accepted")
    return {"case_id": case, "passed": True, "joined_frames": 600,
        "scope": "synthetic CPU audit mechanics only; original pixels and delivery unverified"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt")
    parser.add_argument("--review")
    parser.add_argument("--fixture")
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        require(args.fixture, "CPU fixture path required")
        print(json.dumps(selftest(args.case, args.fixture,
            args.negative_selftest), sort_keys=True))
    else:
        require(args.attempt and args.review, "Original delivery paths required")
        print(json.dumps(audit(args.case, args.attempt, args.review), sort_keys=True))

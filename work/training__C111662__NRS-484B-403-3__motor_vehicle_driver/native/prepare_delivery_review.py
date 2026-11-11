"""Prepare an unapproved source-hashed review worksheet for one original attempt.

This never claims that a feature is visible, that district context is established,
or that the delivered recording has been accepted. A reviewer must complete it
from the original media and retained district/building-use sources.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tempfile

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
INTERSECTION_FLAGS = ("vehicle_and_centerline_visible", "turn_path_visible",
                      "intersection_extent_reviewed", "district_designation_reviewed",
                      "divided_highway_exception_reviewed")
DIVIDED_FLAGS = ("vehicle_and_median_visible", "turn_path_visible",
                 "opening_extent_reviewed", "district_designation_reviewed",
                 "appropriate_crossing_place_reviewed")


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing original review source: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(bundle, attempt, video, output):
    bundle, attempt, video, output = map(Path, (bundle, attempt, video, output))
    config = json.loads((bundle / "config.json").read_text())
    case = config["case_id"]
    if not case.startswith("training__C111662__NRS-484B-403-3__motor_vehicle_driver__"):
        raise ValueError("Wrong selected C111662 case")
    if output.exists():
        raise ValueError("Retain the prior review worksheet; use a fresh output")
    divided = case.endswith(("__divided_reference", "__divided_opening"))
    flags = DIVIDED_FLAGS if divided else INTERSECTION_FLAGS
    value = {"format": ("c111662-4033-divided-original-review-v1" if divided
                         else "c111662-4033-original-review-v1"),
             "source_kind": "original_native_review", "case_id": case,
             "candidate_id": config["candidate_id"], "reviewer_id": "",
             "raw_sha256": sha(attempt / "native-raw-actors.jsonl"),
             "video_frames_sha256": sha(attempt / "video_frames.jsonl"),
             "map_sha256": sha(attempt / "native-map-readback.json"),
             "capture_report_sha256": sha(attempt / "native-capture-report.json"),
             "media_sha256": {name + ".mkv": sha(attempt / (name + ".mkv"))
                              for name in CAMERAS},
             "primary_video_sha256": sha(video),
             "building_use_reviewed": False,
             "district_and_building_use_sources": [], "pixel_boxes": [],
             **{flag: False for flag in flags},
             "review_scope": "Worksheet only. Inspect actual pixels, original geometry, and retained source documents before setting any flag."}
    output.write_text(json.dumps(value, indent=2) + "\n")
    return value


def selftest():
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        cases = ("reference", "contrast", "divided_reference", "divided_opening")
        for suffix in cases:
            bundle, attempt = root / suffix / "bundle", root / suffix / "attempt"
            bundle.mkdir(parents=True)
            attempt.mkdir()
            (bundle / "config.json").write_text(json.dumps({
                "case_id": "training__C111662__NRS-484B-403-3__motor_vehicle_driver__" + suffix,
                "candidate_id": "primary"}))
            for name in ("native-raw-actors.jsonl", "video_frames.jsonl",
                         "native-map-readback.json", "native-capture-report.json",
                         "primary.mkv", *(camera + ".mkv" for camera in CAMERAS)):
                (attempt / name).write_text("synthetic worksheet source: " + name)
            output = attempt / "review-worksheet.json"
            value = prepare(bundle, attempt, attempt / "primary.mkv", output)
            flags = DIVIDED_FLAGS if "divided" in suffix else INTERSECTION_FLAGS
            if (value["reviewer_id"] or value["pixel_boxes"] or
                    value["district_and_building_use_sources"] or
                    any(value[flag] for flag in (*flags, "building_use_reviewed"))):
                raise ValueError("Worksheet made a review claim")
            try:
                prepare(bundle, attempt, attempt / "primary.mkv", output)
            except ValueError:
                pass
            else:
                raise ValueError("Existing review worksheet was overwritten")
    return {"passed": True, "fixture_only": True, "cases": len(cases),
            "unreviewed_flags": True, "accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--bundle")
    parser.add_argument("--attempt")
    parser.add_argument("--video")
    parser.add_argument("--output")
    arguments = parser.parse_args()
    if arguments.selftest:
        print(json.dumps(selftest()))
    else:
        if not all((arguments.bundle, arguments.attempt, arguments.video, arguments.output)):
            parser.error("Original review worksheet needs bundle, attempt, video, output")
        print(json.dumps(prepare(arguments.bundle, arguments.attempt,
                                 arguments.video, arguments.output)))

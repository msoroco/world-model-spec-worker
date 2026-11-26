"""Independent source custody check for a selected driveway attempt.

Diagnostic mode proves the rejection protocol only. Native mode requires the
retained reviewed packet and exact original frame and camera joins. Neither
mode claims legal or pixel visibility acceptance on behalf of a reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ASSIGNMENT = "testing__C229404__LVMC-11-52-130-A7__motor_vehicle_driver"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("mouth", "frontage", "driveway_use", "responsible_person", "relationship",
           "purpose", "traffic_direction", "postal_status")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("missing or escaping original source: " + relative)
    return target


def rows(path):
    result = [json.loads(line) for line in path.read_text().splitlines()]
    if not result:
        raise ValueError("empty original frame series")
    return result


def audit(attempt, case, diagnostic=False):
    root = Path(attempt).resolve()
    if not root.is_dir() or not case.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact selected attempt required")
    original = root / "original-attempt"
    context_path = source(original, "reviewed-context.json")
    trace_path = source(original, "body-control-trace.jsonl")
    receipt_path = source(original, "capture-receipt.json")
    context, receipt = json.loads(context_path.read_text()), json.loads(receipt_path.read_text())
    if (context.get("case_id"), receipt.get("case_id"), receipt.get("assignment_id")) != (case, case, ASSIGNMENT):
        raise ValueError("selected original source identity differs")
    for key, path in (("context_sha256", context_path), ("trace_sha256", trace_path),
                      ("map_sha256", source(root, "road.xodr"))):
        if receipt.get(key) != sha(path):
            raise ValueError("original source bytes changed: " + key)
    if context.get("map_sha256") != receipt["map_sha256"]:
        raise ValueError("reviewed original map differs")
    motion = rows(trace_path)
    if receipt.get("fps") != 20 or receipt.get("frame_count") != len(motion):
        raise ValueError("original capture frame count differs")
    if any(row.get("frame") != i or abs(row.get("time_s", -100) - i / 20) > .002 or
           len(row.get("vehicle_vertices", [])) != 8 for i, row in enumerate(motion)):
        raise ValueError("original body and control trace has missing frames")
    if diagnostic:
        if (receipt.get("source_kind") != "synthetic_fixture" or
                receipt.get("diagnostic_fixture") is not True or
                receipt.get("physical_acceptance_claimed") is not False):
            raise ValueError("diagnostic proof must explicitly reject physical acceptance")
        if any(context.get(name + "_source", {}).get("kind") != "synthetic_diagnostic_only"
               for name in SOURCES):
            raise ValueError("synthetic reviewed context source missing")
        return {"case_id": case, "passed": True, "diagnostic_fixture": True,
                "physical_acceptance": False, "frames": len(motion),
                "receipt_sha256": sha(receipt_path)}
    if receipt.get("source_kind") != "original_native_capture" or receipt.get("diagnostic_fixture") is not False:
        raise ValueError("original Native capture required")
    survey_path = source(original, "original-reviewed-survey.json")
    survey = json.loads(survey_path.read_text())
    if receipt.get("reviewed_survey_sha256") != sha(survey_path) or survey.get("case_id") != case or survey.get("review_status") != "reviewed":
        raise ValueError("retained reviewed survey differs")
    for name in ("opendrive", *SOURCES):
        reference = survey["sources"][name]
        retained = source(original, "reviewed-packet/" + reference["path"])
        if sha(retained) != reference["sha256"]:
            raise ValueError("retained reviewed source changed: " + name)
        if name != "opendrive":
            context_ref = context.get(name + "_source")
            if context_ref is None or context_ref.get("sha256") != reference["sha256"] or context_ref.get("path") != "reviewed-packet/" + reference["path"]:
                raise ValueError("measured context lacks retained reviewed source: " + name)
    if sha(source(original, "reviewed-packet/" + survey["sources"]["opendrive"]["path"])) != sha(source(root, "road.xodr")):
        raise ValueError("Native map not retained from reviewed packet")
    mapping = rows(source(original, "camera-frame-map.jsonl"))
    if len(mapping) != len(motion) or any(
            frame.get("frame") != i or frame.get("carla_frame") != row.get("carla_frame") or
            frame.get("camera_names") != list(CAMERAS)
            for i, (frame, row) in enumerate(zip(mapping, motion))):
        raise ValueError("four original camera streams not joined to motion")
    for name in CAMERAS:
        archive = source(original, name + ".zip")
        if receipt.get("camera_source_sha256", {}).get(name) != sha(archive):
            raise ValueError("original camera source changed: " + name)
    if len(motion) != 900 or receipt.get("restoration_verified") is not True:
        raise ValueError("Native capture or restoration incomplete")
    return {"case_id": case, "passed": True, "diagnostic_fixture": False,
            "physical_acceptance": False, "frames": len(motion),
            "receipt_sha256": sha(receipt_path), "reviewed_survey_sha256": sha(survey_path),
            "actual_pixels_reviewed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()

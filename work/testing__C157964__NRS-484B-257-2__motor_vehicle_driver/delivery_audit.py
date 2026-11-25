"""Independent original-source audit for the subsection 2 officer cases."""

import argparse
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMERAS = {"overview": (1920, 1080), "approach": (1280, 720),
           "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SUFFIXES = ("officer_controls_go", "officer_controls_hold", "officer_present_inactive")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    if not path.is_file():
        raise ValueError("Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt, case_id, diagnostic_fixture=False):
    from worker_exchange.media import audit as audit_video
    from worker_exchange.measurement_contract import validate, verify_report

    attempt = Path(attempt).resolve()
    if case_id not in {HERE.name + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("Wrong exact subsection 2 case")
    suffix = case_id.rsplit("__", 1)[1]
    config, result = read(attempt / "config.json"), read(attempt / "result.json")
    if (config.get("selected_case_id") != case_id or config.get("rate_hz") != 20
            or config.get("duration_s") != 30 or result.get("case_id") != case_id):
        raise ValueError("Exact case or capture profile changed")
    if not diagnostic_fixture and (result.get("provenance_kind") != "native"
                                   or result.get("diagnostic_fixture")):
        raise ValueError("Native original provenance required")
    mapping = rows(attempt / "video_frames.jsonl")
    history = rows(attempt / "officer_history.jsonl")
    trace = rows(attempt / "trace.jsonl")
    review = read(attempt / "officer_review.json")
    receipt = read(attempt / "capture-receipt.json")
    expected = 3 if diagnostic_fixture else 600
    if not all(len(seq) == expected for seq in (mapping, history, trace, review.get("frames", []), receipt.get("rows", []))):
        raise ValueError("Full original frame, actor, trace and review streams required")
    if receipt.get("case_id") != case_id or receipt.get("frame_count") != expected or review.get("case_id") != case_id:
        raise ValueError("Original capture or reviewer case mismatch")
    for i, (frame, actor, vehicle, review_frame, capture) in enumerate(zip(
            mapping, history, trace, review["frames"], receipt["rows"])):
        native = frame.get("carla_frame")
        time_s = frame.get("time_s")
        if (frame.get("video_frame") != i or type(native) is not int
                or not isinstance(time_s, (int, float)) or not math.isfinite(time_s)
                or actor.get("frame") != native or vehicle.get("frame") != native
                or review_frame.get("carla_frame") != native or capture.get("carla_frame") != native):
            raise ValueError("Original frame join changed")
        if i and (native != mapping[i-1]["carla_frame"] + 1
                  or abs(time_s - mapping[i-1]["time_s"] - .05) > .001):
            raise ValueError("Original 20 Hz frame sequence changed")
        if (not actor.get("ego", {}).get("body_vertices_xy_m")
                or not actor.get("other_body_vertices_xy_m")):
            raise ValueError("Original complete-body geometry missing")
        for key in ("officer_direction_observed", "traffic_control_observed",
                    "other_approaching_observed", "officer_actor_id"):
            if actor.get(key) != review_frame.get(key):
                raise ValueError("Original reviewer and actor history disagree: " + key)
        for camera in CAMERAS:
            reference = camera + ".mkv#frame-" + str(i)
            if capture.get("native_actor_source", {}).get("camera_raw_sources", {}).get(camera) != reference:
                raise ValueError("Original capture camera reference changed")
    for camera, dimensions in CAMERAS.items():
        source = attempt / (camera + ".mkv")
        if review.get("camera_sha256", {}).get(camera) != sha(source):
            raise ValueError("Original camera source hash changed: " + camera)
        decoded = audit_video(source, expected, mapping_sha256=sha(attempt / "video_frames.jsonl"))
        if decoded.get("dimensions") != list(dimensions):
            raise ValueError("Original camera dimensions changed: " + camera)
    report = read(attempt / "analysis-report.json")
    for name, digest in report.get("source_report", {}).get("sources", {}).items():
        if name not in ("officer_context.json", "officer_history.jsonl", "video_frames.jsonl") or sha(attempt / name) != digest:
            raise ValueError("Saved analysis source binding changed")
    plan = read(HERE / "case-plan.json")
    contract = read(HERE / (suffix + "-measurement-contract.json"))
    validate(contract, plan["requirement_dispositions"], (HERE / "finalizer.py").read_text(), case_id)
    measured = verify_report(contract, report, attempt)
    if len(measured) != 5:
        raise ValueError("Five selected source-bound measurements required")
    if (report.get("physical_acceptance_claimed") or report.get("legal_conclusion") != "unresolved"
            or result.get("physical_acceptance_claimed")):
        raise ValueError("Software sources claim physical or legal acceptance")
    if not diagnostic_fixture and (result.get("physical_checks", {}).get("setup", {}).get("status") != "met"
                                   or result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"):
        raise ValueError("Original physical setup and maneuver not confirmed")
    return {"format": "worker-c157964-sub2-independent-source-audit", "case_id": case_id,
            "diagnostic_fixture": diagnostic_fixture, "original_frames": expected,
            "frame_map_sha256": sha(attempt / "video_frames.jsonl"),
            "actor_history_sha256": sha(attempt / "officer_history.jsonl"),
            "sealed_result_sha256": sha(attempt / "result.json"),
            "analysis_sha256": sha(attempt / "analysis-report.json"),
            "verified_measurements": sorted(measured), "software_audit_passed": True,
            "physical_acceptance_claimed": False, "legal_conclusion": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(audit(arguments.attempt, arguments.case, arguments.diagnostic_fixture), indent=2))

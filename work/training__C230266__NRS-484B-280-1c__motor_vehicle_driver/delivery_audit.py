"""Independent source and pixel audit for NRS 484B.280(1)(c) delivery.

The CPU self test checks rejection rules only. A real audit requires the exact
original Native attempt, a separate reviewer record, and decoded source video.
"""

import argparse
import hashlib
import json
from pathlib import Path


CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")
POSITION_SOURCES = {
    "road": ("road_boundary_source", "pedestrian_position_source"),
    "bus_stop": ("bus_stop_designation_source", "bus_stop_geometry_source", "pedestrian_position_source"),
    "bench": ("bench_geometry_source", "bench_public_mass_transport_use_source", "pedestrian_position_source"),
    "shelter": ("shelter_geometry_source", "shelter_public_mass_transport_use_source", "pedestrian_position_source"),
    "transit_stop": ("stop_designation_source", "stop_furniture_geometry_source", "pedestrian_position_source"),
    "boarding": ("transit_vehicle_class_source", "door_side_source", "boarding_motion_source"),
    "other_transport": ("other_public_transport_class_source", "door_side_source", "boarding_motion_source"),
    "school_zone": ("school_zone_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "school_crossing": ("school_crossing_sign_source", "governed_zone_extent_source", "pedestrian_position_source"),
    "marked_crosswalk": ("marked_crosswalk_source", "pedestrian_position_source"),
    "unmarked_crosswalk": ("intersection_and_sidewalk_source", "unmarked_crossing_limits_source", "pedestrian_position_source"),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, relative):
    file = (root / relative).resolve()
    if root.resolve() not in file.parents or not file.is_file():
        raise ValueError("Missing original source: " + relative)
    return file


def lines(path):
    return [json.loads(row) for row in path.read_text().splitlines() if row.strip()]


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "native"
            or result.get("diagnostic_fixture") is not False):
        raise ValueError("Missing original source: exact Native result")
    if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"
            or result.get("maneuver_completed") is not True):
        raise ValueError("Original physical travel completion unverified")
    facts = result.get("measured_values", {})
    if (facts.get("frames") != 600 or facts.get("branch") not in POSITION_SOURCES
            or facts.get("position_evidenced_frames", 0) < 1
            or facts.get("first_actual_observation_frame") is None
            or facts.get("proper_caution_legal_verdict") is not None):
        raise ValueError("Original statutory position or driver observation unverified")
    if result.get("accepted") is not False or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Source finalizer preaccepted the legal outcome")
    return facts["branch"]


def check_review(review, case, sources, branch):
    if (review.get("format") != "worker-nrs280-independent-source-review-v1"
            or review.get("case_id") != case or not review.get("reviewer_id")
            or review.get("branch") != branch):
        raise ValueError("Missing independent original pedestrian review")
    for name, path in sources.items():
        if review.get("source_sha256", {}).get(name) != sha(path):
            raise ValueError("Independent review source changed: " + name)
    if not all(review.get(name) is True for name in
               ("pedestrian_identity_reviewed", "statutory_position_reviewed",
                "actual_driver_observation_source_reviewed", "actual_pixels_reviewed")):
        raise ValueError("Original identity, position, observation or pixels unreviewed")
    if not review.get("source_documentation") or review.get("legal_verdict_claimed") is True:
        raise ValueError("Independent review lacks original documentation or prelabels law")
    frames = review.get("reviewed_frames", [])
    if not frames or any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError("Decisive original pixel frames missing")


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError("Independent auditor must run in local operations")
    result_path = inside(attempt, "result.json")
    result = json.loads(result_path.read_text())
    branch = check_result(result, args.case)
    source_names = ("pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl",
                    "context-survey.json", "video_frames.jsonl", "driver_reference.mkv",
                    "reference_corner.mkv")
    sources = {name: inside(attempt, name) for name in source_names}
    survey = json.loads(sources["context-survey.json"].read_text())
    if (survey.get("source_kind") != "original_native_context_survey" or
            survey.get("diagnostic_fixture") is True or
            any(not survey.get(key) for key in POSITION_SOURCES[branch])):
        raise ValueError("Missing independently sourced statutory position")
    review = json.loads(inside(attempt, args.review).read_text())
    check_review(review, args.case, sources, branch)
    capture = lines(sources["pedestrian-caution-trace.jsonl"])
    checked = lines(sources["pedestrian-source-review.jsonl"])
    mapping = lines(sources["video_frames.jsonl"])
    if len(capture) != len(checked) or len(checked) != len(mapping) or len(mapping) != 600:
        raise ValueError("Original frame count differs")
    for index, (row, source, frame) in enumerate(zip(capture, checked, mapping)):
        if (row.get("frame") != index or row.get("native_frame") != frame.get("native_frame")
                or source.get("native_frame") != frame.get("native_frame")
                or row.get("video_frame") != index or source.get("video_frame") != index
                or row.get("time_s") != frame.get("time_s")):
            raise ValueError("Original pose/review/video time join differs")
    if not any(row.get("driver_observed_pedestrian") is True and
               row.get("driver_observation_source") for row in checked):
        raise ValueError("Actual driver observation has no separate source")
    video = inside(attempt, args.video)
    trace = inside(attempt, args.trace)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(video, 600, mapping_sha256=sha(sources["video_frames.jsonl"]), receipt=decode)
    verified = media.verify_receipt(video, decode, 600,
                                    mapping_sha256=sha(sources["video_frames.jsonl"]))
    proof = {"format": "worker-delivery-audit", "passed": True,
             "case_id": args.case, "job_id": args.job,
             "attempt": args.attempt_number, "recording_id": args.recording_id,
             "source_result_sha256": sha(result_path), "frames": 600,
             "video": args.video, "video_sha256": sha(video),
             "trace": args.trace, "trace_sha256": sha(trace),
             "checks": {key: True for key in CHECKS},
             "auditor_path": str(Path(__file__).resolve()),
             "auditor_sha256": sha(Path(__file__).resolve()),
             "source_decode_receipt_path": str(decode),
             "source_decode_receipt_sha256": sha(decode),
             "source_decode_auditor_sha256": verified["auditor_sha256"],
             "independent_review_sha256": sha(inside(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case, negative):
    result = {"case_id": case, "provenance_kind": "native", "diagnostic_fixture": False,
              "physical_checks": {"maneuver": {"status": "met"}},
              "maneuver_completed": True, "accepted": False,
              "legal_verdict_claimed": False,
              "measured_values": {"frames": 600, "branch": "road",
                                  "position_evidenced_frames": 100,
                                  "first_actual_observation_frame": 150,
                                  "proper_caution_legal_verdict": None}}
    if negative:
        result["measured_values"]["first_actual_observation_frame"] = None
        check_result(result, case)
        raise AssertionError("Missing driver observation accepted")
    check_result(result, case)
    for branch in POSITION_SOURCES:
        changed = json.loads(json.dumps(result))
        changed["measured_values"]["branch"] = branch
        check_result(changed, case)
    for key, value in (("provenance_kind", "synthetic_fixture"),
                       ("maneuver_completed", False), ("accepted", True)):
        changed = json.loads(json.dumps(result))
        changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing source or physical state accepted: " + key)
    return {"case_id": case, "source_predicates_tested": True,
            "original_capture_attested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--operations")
    parser.add_argument("--output")
    parser.add_argument("--trace", default="converted/trace.json")
    parser.add_argument("--video", default="primary.mkv")
    parser.add_argument("--review", default="independent-review.json")
    parser.add_argument("--job", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args)))

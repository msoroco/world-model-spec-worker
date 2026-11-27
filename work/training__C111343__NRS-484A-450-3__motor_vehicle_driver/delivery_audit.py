"""Independent saved original-source audit for a conditional yield stop."""

import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing original source: " + name)
    return path


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "native"
            or result.get("diagnostic_fixture") is not False):
        raise ValueError("Exact original Native result missing")
    metric = result.get("measured_values", {})
    if (metric.get("frame_count") != 600 or metric.get("safety_stop_requirement") != "unassessed"
            or metric.get("legal_compliance") != "unassessed"):
        raise ValueError("Original conditional-stop measurement or unresolved judgment missing")
    expected = case.endswith("__before_crosswalk")
    if metric.get("first_stop_before_crosswalk") is not expected:
        raise ValueError("Measured first stop differs from exact case")
    if expected is False and metric.get("first_stop_in_crosswalk") is not True:
        raise ValueError("Past-crosswalk case lacks measured within-crosswalk stop")
    if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or
            result.get("maneuver_completed") is not True):
        raise ValueError("Original physical traversal unproven")
    return metric


def check_review(review, case):
    if (review.get("format") != "c111343-yield-crosswalk-original-review-v1" or
            review.get("source_kind") != "original_native_review" or
            review.get("case_id") != case or not review.get("reviewer_id")):
        raise ValueError("Original pixel and safety review missing")
    for key in ("yield_sign_governs_visible", "near_crosswalk_visible",
                "both_vehicle_bodies_visible", "first_stop_position_visible",
                "intersecting_traffic_reviewed", "safety_stop_required_for_this_approach"):
        if type(review.get(key)) is not bool:
            raise ValueError("Original review finding missing: " + key)
    if not all(review[key] for key in ("yield_sign_governs_visible", "near_crosswalk_visible",
                                   "both_vehicle_bodies_visible", "first_stop_position_visible",
                                   "intersecting_traffic_reviewed", "safety_stop_required_for_this_approach")):
        raise ValueError("Original physical or conditional safety premise unconfirmed")
    if not review.get("safety_reason") or not review.get("source_sha256"):
        raise ValueError("Safety judgment lacks original source and reason")


def audit(args):
    from worker_exchange import media
    root = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    if output.exists():
        raise ValueError("Retain prior independent audit")
    result_path = source(root, "result.json")
    metric = check_result(read(result_path), args.case)
    context = read(source(root, "yield_context.json"))
    if (context.get("source_kind") != "original_native_yield_crosswalk_readback" or
            context.get("safety_stop_required") != "unassessed"):
        raise ValueError("Original source context or unresolved safety state differs")
    for key, name in context.get("source_files", {}).items():
        if sha(source(root, name)) != context.get(key + "_sha256"):
            raise ValueError("Original source hash differs: " + key)
    frames = [json.loads(line) for line in source(root, "video_frames.jsonl").read_text().splitlines()]
    motion = [json.loads(line) for line in source(root, "yield_motion.jsonl").read_text().splitlines()]
    ego = [json.loads(line) for line in source(root, "ego_body.jsonl").read_text().splitlines()]
    other = [json.loads(line) for line in source(root, "intersecting_body.jsonl").read_text().splitlines()]
    if any(len(group) != 600 for group in (frames, motion, ego, other)):
        raise ValueError("Original four-source frame inventory incomplete")
    for i, (frame, state, subject, intersecting) in enumerate(zip(frames, motion, ego, other)):
        native = frame.get("native_frame")
        if (frame.get("video_frame") != i or state.get("video_frame") != i or
                state.get("native_frame") != native or subject.get("native_frame") != native or
                intersecting.get("native_frame") != native or
                state.get("ego_actor_id") != subject.get("actor_id") or
                state.get("intersecting_actor_id") != intersecting.get("actor_id") or
                frame.get("source_cameras") != {name: native for name in CAMERAS} or
                len(subject.get("body_vertices_m", [])) < 4 or
                len(intersecting.get("body_vertices_m", [])) < 4):
            raise ValueError("Original actor, body, clock or camera join differs")
    review_path = source(root, args.review)
    review = read(review_path)
    check_review(review, args.case)
    for name, checksum in review["source_sha256"].items():
        if sha(source(root, name)) != checksum:
            raise ValueError("Original review source hash differs: " + name)
    required_media = {name + ".mkv" for name in CAMERAS} | {"raw.mkv"}
    if set(review.get("media_sha256", {})) != required_media:
        raise ValueError("Original camera and composed media inventory incomplete")
    for name, checksum in review["media_sha256"].items():
        if sha(source(root, name)) != checksum:
            raise ValueError("Original reviewed media hash differs: " + name)
    mapping = source(root, "video_frames.jsonl")
    video = source(root, args.video)
    receipt = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    decode = media.audit(video, 600, mapping_sha256=sha(mapping), receipt=receipt)
    media.verify_receipt(video, receipt, 600, mapping_sha256=sha(mapping))
    trace = read(source(root, args.trace))
    scenes = trace.get("scenes", [])
    if len(scenes) != 600 or any(scene.get("t") != round(frame["time_s"] * 1000)
                                 for scene, frame in zip(scenes, frames)):
        raise ValueError("Core and original frame time join differs")
    report = {"format": "worker-delivery-audit", "passed": True,
        "case_id": args.case, "job_id": args.job, "recording_id": args.recording_id,
        "source_result_sha256": sha(result_path), "video_sha256": sha(video),
        "trace_sha256": sha(source(root, args.trace)), "human_review_sha256": sha(review_path),
        "source_decode_sha256": sha(receipt), "decoded_frames": decode["frames"],
        "measurement": {"first_stop_front_x_m": metric["first_stop_front_x_m"],
                        "safety_stop_required": "independently_reviewed_true"},
        "checks": {name: True for name in CHECKS},
        "physical_or_legal_acceptance_claimed_by_fixture": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


def selftest(case, negative):
    metric = {"frame_count": 600, "first_stop_front_x_m": -9 if case.endswith("__before_crosswalk") else -4,
              "first_stop_before_crosswalk": case.endswith("__before_crosswalk"),
              "first_stop_in_crosswalk": case.endswith("__past_crosswalk"),
              "safety_stop_requirement": "unassessed", "legal_compliance": "unassessed"}
    sample = {"case_id": case, "provenance_kind": "native", "diagnostic_fixture": False,
              "measured_values": metric, "maneuver_completed": True,
              "physical_checks": {"maneuver": {"status": "met"}}}
    if negative:
        sample["provenance_kind"] = "synthetic_fixture"
        check_result(sample, case)
        raise AssertionError("Synthetic source unexpectedly accepted")
    check_result(sample, case)
    review = {"format": "c111343-yield-crosswalk-original-review-v1",
        "source_kind": "original_native_review", "case_id": case,
        "reviewer_id": "cpu-schema-only", "yield_sign_governs_visible": True,
        "near_crosswalk_visible": True, "both_vehicle_bodies_visible": True,
        "first_stop_position_visible": True, "intersecting_traffic_reviewed": True,
        "safety_stop_required_for_this_approach": True,
        "safety_reason": "CPU schema probe only; not an original finding",
        "source_sha256": {"yield_context.json": "schema-only"}}
    check_review(review, case)
    print(json.dumps({"case_id": case, "cpu_predicates_passed": True,
                      "original_acquisition_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    for name in ("attempt", "output", "video", "trace", "review", "job", "recording-id"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    selftest(args.case, args.negative) if args.self_test else audit(args)

"""Independent original-source and pixel audit for NRS 486.341 delivery.

CPU self tests exercise rejection branches. Real acceptance requires the sealed
Native attempt, saved result, independent review and original source video.
"""

import argparse
import hashlib
import json
from pathlib import Path


CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED_CONTEXT = ("highway_public_maintenance_source",
                    "highway_public_vehicular_access_source",
                    "protected_vehicle_seat_source", "protected_vehicle_wheels_source",
                    "protected_vehicle_exclusions_source",
                    "subject_motor_vehicle_class_source")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + name)
    return path


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "native"
            or result.get("diagnostic_fixture") is not False):
        raise ValueError("Missing original source: exact Native result")
    if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"
            or result.get("maneuver_completed") is not True
            or result.get("measured_values", {}).get("frame_count") != 600):
        raise ValueError("Original physical travel completion unverified")
    if result.get("accepted") is not False or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Source finalizer preaccepted a legal outcome")


def check_review(review, case, sources):
    if (review.get("format") != "worker-nrs486-independent-source-review-v1"
            or review.get("case_id") != case or not review.get("reviewer_id")
            or review.get("legal_verdict_claimed") is not False):
        raise ValueError("Missing independent chapter 486 source review")
    for name, path in sources.items():
        if review.get("source_sha256", {}).get(name) != sha(path):
            raise ValueError("Independent source review changed: " + name)
    for key in ("highway_public_maintenance_reviewed", "highway_public_access_reviewed",
                "protected_classification_reviewed", "subject_classification_reviewed",
                "all_participants_reviewed", "actual_pixels_reviewed",
                "lane_occupancy_reviewed"):
        if review.get(key) is not True:
            raise ValueError("Independent source review incomplete: " + key)
    if not review.get("source_documentation") or not review.get("reviewed_frames"):
        raise ValueError("Independent original pixel documentation missing")
    if any(type(frame) is not int or frame < 0 or frame >= 600
           for frame in review["reviewed_frames"]):
        raise ValueError("Independent reviewed frame identity invalid")


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or operations not in output.parents:
        raise ValueError("Independent auditor must run in local operations")
    result_path = inside(attempt, "result.json")
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    names = ("lane-use-source.jsonl", "lane-use-context.json", "road-authority.json",
             "video_frames.jsonl", "trace.jsonl", *(name + ".mkv" for name in VIEWS))
    sources = {name: inside(attempt, name) for name in names}
    context = json.loads(sources["lane-use-context.json"].read_text())
    if (context.get("source_kind") != "original_native_context_survey"
            or context.get("diagnostic_fixture_only") is True
            or any(not context.get(key) for key in REQUIRED_CONTEXT)):
        raise ValueError("Original chapter 486 highway or classification source missing")
    review = json.loads(inside(attempt, args.review).read_text())
    check_review(review, args.case, sources)
    geometry = lines(sources["lane-use-source.jsonl"])
    mapping = lines(sources["video_frames.jsonl"])
    if len(geometry) != 600 or len(mapping) != 600:
        raise ValueError("Original frame coverage differs")
    pairs = set()
    for index, (row, frame) in enumerate(zip(geometry, mapping)):
        if (row.get("frame") != index or row.get("video_frame") != index
                or frame.get("video_frame") != index
                or row.get("native_frame") != frame.get("native_frame")
                or row.get("time_s") != frame.get("time_s")
                or set(frame.get("camera_native_frames", {})) != set(VIEWS)
                or any(value != row["native_frame"]
                       for value in frame["camera_native_frames"].values())):
            raise ValueError("Original actor and camera time join differs")
        pairs.add((row.get("ego_actor_id"), row.get("motorcycle_actor_id")))
    if len(pairs) != 1 or any(not a or not b or a == b for a, b in pairs):
        raise ValueError("Original subject and motorcycle identities differ")
    source_receipts = {}
    for name in VIEWS:
        video = sources[name + ".mkv"]
        receipt = output.with_name("source-" + name + "-" + args.case.rsplit("__", 1)[-1] + ".json")
        media.audit(video, 600, mapping_sha256=sha(sources["video_frames.jsonl"]),
                    receipt=receipt)
        media.verify_receipt(video, receipt, 600,
                             mapping_sha256=sha(sources["video_frames.jsonl"]))
        source_receipts[name] = {"video_sha256": sha(video),
                                 "decode_receipt_sha256": sha(receipt)}
    video = inside(attempt, args.video)
    trace = inside(attempt, args.trace)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(video, 600, mapping_sha256=sha(sources["video_frames.jsonl"]),
                receipt=decode)
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
             "source_video_receipts": source_receipts,
             "actor_ids": list(next(iter(pairs))),
             "independent_review_sha256": sha(inside(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case, negative=False):
    result = {"case_id": case, "provenance_kind": "native",
              "diagnostic_fixture": False, "physical_checks": {"maneuver": {"status": "met"}},
              "maneuver_completed": True, "measured_values": {"frame_count": 600},
              "accepted": False, "legal_verdict_claimed": False}
    if negative:
        result["measured_values"]["frame_count"] = 0
        check_result(result, case)
        raise AssertionError("Incomplete Native frame count accepted")
    check_result(result, case)
    for key, value in (("provenance_kind", "synthetic_fixture"),
                       ("maneuver_completed", False), ("accepted", True)):
        changed = json.loads(json.dumps(result))
        changed[key] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid original state accepted: " + key)
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

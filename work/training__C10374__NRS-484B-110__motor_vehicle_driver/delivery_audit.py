"""Independent source and human-review audit for the original C10374 attempt.

Copy into local state/operations/worker_exchange before actual acceptance.
Self-tests only test rejection predicates; they do not attest physical footage.
"""

import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(root, rel):
    path = (root / rel).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + str(rel))
    return path


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "original_native"
            or result.get("diagnostic_fixture") is True):
        raise ValueError("Missing original source: exact original Native result")
    if (result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met"
            or result.get("maneuver_completed") is not True):
        raise ValueError("Original route completion not established")
    if result.get("physical_checks", {}).get("setup", {}).get("status") != "met":
        raise ValueError("Original safety-zone setup not established")
    if not result.get("realized_observables"):
        raise ValueError("Missing measured original motion")
    required = {"kin.speed", "zone_body"}
    observed = {row.get("name") for row in result.get("recording_evidence", [])}
    if not required <= observed:
        raise ValueError("Missing original body or speed observation")


def check_review(review, case, frame_map):
    if (review.get("format") != "c10374-original-zone-review-v1"
            or review.get("source_kind") != "original_native_review"
            or review.get("case_id") != case or not review.get("reviewer_id")):
        raise ValueError("Missing source-bound original zone review")
    if review.get("video_frames_sha256") != sha(frame_map):
        raise ValueError("Original zone review changed frame map")
    if review.get("official_safety_zone_designation_verified") is not True:
        raise ValueError("Official safety-zone designation unverified")
    rows = frame_map.read_text().splitlines()
    pixels = review.get("frame_visibility", {})
    if len(rows) != 600 or set(pixels) != {str(i) for i in range(len(rows))}:
        raise ValueError("Missing reviewed original pixels")
    if any(type(row.get("vehicle_visible")) is not bool or
           type(row.get("zone_boundary_visible")) is not bool for row in pixels.values()):
        raise ValueError("Incomplete vehicle or zone original pixel review")


def check_join(frame_map, trace):
    frames = [json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes = json.loads(trace.read_text()).get("scenes", [])
    if len(frames) != 600 or len(scenes) != 600:
        raise ValueError("Original frame/Core count mismatch")
    for index, (frame, scene) in enumerate(zip(frames, scenes)):
        if frame.get("video_frame") != index or scene.get("t") != round(frame["time_s"] * 1000):
            raise ValueError("Original frame/Core timestamp mismatch")
    return len(frames)


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    operations = Path(args.operations).resolve()
    output = Path(args.output).resolve()
    if operations not in Path(__file__).resolve().parents or Path(__file__).name != "delivery_audit.py":
        raise ValueError("Independent auditor must run from local operations")
    if operations not in output.parents:
        raise ValueError("Audit output must stay in local operations")
    result_path = inside(attempt, "result.json")
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    frame_map = inside(attempt, "video_frames.jsonl")
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    review = inside(attempt, args.review)
    check_review(json.loads(review.read_text()), args.case, frame_map)
    for row in result["recording_evidence"]:
        inside(attempt, row["reference"])
    frames = check_join(frame_map, trace)
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(video, frames, mapping_sha256=sha(frame_map), receipt=decode)
    verified = media.verify_receipt(video, decode, frames, mapping_sha256=sha(frame_map))
    payload = {"format": "worker-delivery-audit", "passed": True, "case_id": args.case,
               "job_id": args.job, "attempt": args.attempt_number, "recording_id": args.recording_id,
               "source_result_sha256": sha(result_path), "frames": frames,
               "video": args.video, "video_sha256": sha(video), "trace": args.trace,
               "trace_sha256": sha(trace), "checks": {name: True for name in CHECKS},
               "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(Path(__file__).resolve()),
               "source_decode_receipt_path": str(decode), "source_decode_receipt_sha256": sha(decode),
               "source_decode_auditor_sha256": verified["auditor_sha256"],
               "human_review_sha256": sha(review), "physical_acceptance_claimed_by_fixture": False}
    output.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def selftest(case, negative):
    sample = {"case_id": case, "provenance_kind": "original_native", "diagnostic_fixture": False,
              "maneuver_completed": True, "physical_checks": {"maneuver": {"status": "met"},
               "setup": {"status": "met"}}, "realized_observables": {"progress_m": 20},
              "recording_evidence": [{"name": "kin.speed"}, {"name": "zone_body"}]}
    if negative:
        sample["provenance_kind"] = "synthetic_fixture"
        check_result(sample, case)
        raise AssertionError("synthetic source accepted")
    check_result(sample, case)
    for field, value, fragment in (("maneuver_completed", False, "Original route"),
                                   ("realized_observables", {}, "Missing measured")):
        changed = json.loads(json.dumps(sample))
        changed[field] = value
        try:
            check_result(changed, case)
        except ValueError as error:
            assert fragment in str(error)
        else:
            raise AssertionError("Missing original source accepted")
    return {"case_id": case, "source_predicates_tested": True, "original_capture_attested": False}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--case", required=True)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--negative", action="store_true")
    p.add_argument("--attempt")
    p.add_argument("--operations")
    p.add_argument("--output")
    p.add_argument("--trace", default="converted/trace.json")
    p.add_argument("--video", default="primary.mkv")
    p.add_argument("--review", default="human-review.json")
    p.add_argument("--job", type=int)
    p.add_argument("--attempt-number", type=int)
    p.add_argument("--recording-id")
    args = p.parse_args()
    print(json.dumps(selftest(args.case, args.negative) if args.self_test else audit(args), indent=2))

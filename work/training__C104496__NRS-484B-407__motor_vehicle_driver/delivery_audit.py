"""Independent original-source audit for one C104496 delivery attempt.

Copy this file into the local batch operations directory before use. CPU self-tests
exercise rejection logic only and make no physical acceptance claim.
"""
import argparse
import hashlib
import json
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode", "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def inside(root, rel):
    path = (root / rel).resolve()
    if root.resolve() not in path.parents:
        raise ValueError("Source escapes original attempt")
    if not path.is_file():
        raise ValueError("Missing original source: " + str(rel))
    return path


def check_result(result, case):
    if result.get("case_id") != case or result.get("provenance_kind") != "original_native" or result.get("diagnostic_fixture") is True:
        raise ValueError("Missing original source: exact original Native result")
    if result.get("maneuver_completed") is not True or result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met":
        raise ValueError("Physical reversal completion not established")
    if result.get("physical_checks", {}).get("setup", {}).get("status") != "met":
        raise ValueError("Original setup not established")
    names = {row.get("name") for row in result.get("recording_evidence", [])}
    required = {"curve_geometry", "grade_profile", "reversal_motion", "two_direction_visibility", "source_camera_views", "native_body_pose_control", "camera_frame_join"}
    if not required <= names:
        raise ValueError("Missing original participant or observation channel")
    if not result.get("realized_observables"):
        raise ValueError("Missing measured original motion")


def check_review(review, case, result, attempt, mapping):
    if review.get("format") != "c104496-original-human-review-v1" or review.get("source_kind") != "original_native_review" or review.get("case_id") != case or not review.get("reviewer_id"):
        raise ValueError("Missing source-bound original pixel review")
    if review.get("video_frames_sha256") != sha(mapping):
        raise ValueError("Original pixel review changed frame map")
    requests = [json.loads(line) for line in inside(attempt, "requested-tracks.jsonl").read_text().splitlines()]
    if len(requests) != len(mapping.read_text().splitlines()):
        raise ValueError("Original request/frame join incomplete")
    expected = {str(i) for i, row in enumerate(requests) if row.get("requested_motion_phase") in ("forward_left", "reverse_right", "forward_left_finish")}
    observed = review.get("turn_frame_visibility", {})
    if not expected or not expected <= set(observed):
        raise ValueError("Missing reviewed reversal frames")
    for key in expected:
        row = observed[key]
        if type(row.get("west_visible")) is not bool or type(row.get("east_visible")) is not bool:
            raise ValueError("Incomplete two-direction original pixel review")
    for row in result.get("recording_evidence", []):
        inside(attempt, row["reference"])


def check_join(mapping, trace):
    scenes = load(trace).get("scenes", [])
    rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if not scenes or len(rows) != len(scenes):
        raise ValueError("Original frame/Core count mismatch")
    for index, (row, scene) in enumerate(zip(rows, scenes)):
        if row.get("video_frame") != index or scene.get("t") != round(row["time_s"] * 1000):
            raise ValueError("Original frame/Core timestamp mismatch")
    return len(scenes)


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    operations = Path(args.operations).resolve()
    if operations not in Path(__file__).resolve().parents or Path(__file__).name != "delivery_audit.py":
        raise ValueError("Independent auditor must run from local operations")
    if operations not in output.parents:
        raise ValueError("Audit output must stay in local operations")
    result_path = inside(attempt, "result.json")
    result = load(result_path)
    check_result(result, args.case)
    mapping = inside(attempt, "video_frames.jsonl")
    trace = inside(attempt, args.trace)
    video = inside(attempt, args.video)
    review_path = inside(attempt, args.review)
    review = load(review_path)
    check_review(review, args.case, result, attempt, mapping)
    frames = check_join(mapping, trace)
    if frames != args.frames:
        raise ValueError("Original frame count differs from plan")
    output.parent.mkdir(parents=True, exist_ok=True)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(video, frames, mapping_sha256=sha(mapping), receipt=decode)
    verified = media.verify_receipt(video, decode, frames, mapping_sha256=sha(mapping))
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"format": "worker-delivery-audit", "passed": True, "case_id": args.case,
               "job_id": args.job, "attempt": args.attempt_number, "recording_id": args.recording_id,
               "source_result_sha256": sha(result_path), "frames": frames,
               "video": args.video, "video_sha256": sha(video), "trace": args.trace,
               "trace_sha256": sha(trace), "checks": {key: True for key in CHECKS},
               "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(Path(__file__).resolve()),
               "source_decode_receipt_path": str(decode), "source_decode_receipt_sha256": sha(decode),
               "source_decode_auditor_sha256": verified["auditor_sha256"],
               "human_review_sha256": sha(review_path), "physical_acceptance_claimed_by_fixture": False}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return payload


def selftest(case, negative):
    sample = {"case_id": case, "provenance_kind": "original_native", "diagnostic_fixture": False,
              "maneuver_completed": True, "physical_checks": {"maneuver": {"status": "met"}, "setup": {"status": "met"}},
              "recording_evidence": [{"name": name} for name in ("curve_geometry", "grade_profile", "reversal_motion", "two_direction_visibility", "source_camera_views", "native_body_pose_control", "camera_frame_join")],
              "realized_observables": {"sampled_path_m": 1}}
    if negative:
        sample["provenance_kind"] = "synthetic_fixture"
        check_result(sample, case)
        raise AssertionError("synthetic source was not rejected")
    check_result(sample, case)
    for field, error in (("maneuver_completed", "Physical reversal"), ("realized_observables", "Missing measured")):
        changed = json.loads(json.dumps(sample))
        changed[field] = False if field == "maneuver_completed" else {}
        try:
            check_result(changed, case)
        except ValueError as exc:
            if error not in str(exc):
                raise
        else:
            raise AssertionError("missing evidence accepted: " + field)
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
    p.add_argument("--frames", type=int, default=700)
    a = p.parse_args()
    print(json.dumps(selftest(a.case, a.negative) if a.self_test else audit(a), indent=2))

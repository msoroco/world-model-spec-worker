"""Independent original-source acceptance audit for the C111331 steady-red pair."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")
SOURCE_NAMES = ("steady-red-native-samples.jsonl", "signal_survey.json", "trace.jsonl",
                "video_frames.jsonl", "overview.mkv", "approach.mkv",
                "reference_corner.mkv", "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    if root not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_result(result, case):
    if (result.get("case_id") != case or result.get("provenance_kind") != "native"
            or result.get("diagnostic_fixture") is not False):
        raise ValueError("Missing original source: exact Native result")
    if result.get("physical_checks", {}).get("maneuver", {}).get("status") != "met" or result.get("maneuver_completed") is not True:
        raise ValueError("Original physical completion unverified")
    if result.get("accepted") is not False or result.get("legal_verdict_claimed") is not False:
        raise ValueError("Source finalizer preaccepted the legal outcome")
    measured = result.get("measured_values", {})
    if measured.get("first_green_frame") is None or not result.get("target_checks"):
        raise ValueError("Original governing signal or target measurement unverified")


def check_review(review, case, paths):
    if (review.get("format") != "worker-c111331-independent-red-review-v1"
            or review.get("case_id") != case or not review.get("reviewer_id")
            or review.get("legal_verdict_claimed") is not False):
        raise ValueError("Missing independent signal and stop-reference review")
    if any(review.get("source_sha256", {}).get(name) != sha(path) for name, path in paths.items()):
        raise ValueError("Independent review source changed")
    required = ("governing_head_facing_reviewed", "stop_reference_hierarchy_reviewed",
                "full_body_halt_and_crossing_reviewed", "actual_pixels_reviewed")
    if any(review.get(key) is not True for key in required):
        raise ValueError("Original signal, stop reference, motion or pixels unreviewed")
    if not review.get("source_documentation") or not review.get("reviewed_frames"):
        raise ValueError("Independent original review lacks documented decisive frames")
    if any(type(frame) is not int or frame < 0 or frame >= 480 for frame in review["reviewed_frames"]):
        raise ValueError("Independent review frame outside original recording")


def audit(args):
    import os
    repo = Path(__file__).resolve().parents[1].parent
    os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(repo / ".runtime-work" / "c111331-audit-output"))
    sys.path[:0] = [str(repo / "runtime"), str(repo / "runtime/scenario_pipeline")]
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    operations = Path(args.operations).resolve()
    if operations not in output.parents or operations not in Path(__file__).resolve().parents:
        raise ValueError("Independent auditor must run in local operations")
    result_path = source(attempt, "result.json")
    result = json.loads(result_path.read_text())
    check_result(result, args.case)
    paths = {name: source(attempt, name) for name in SOURCE_NAMES}
    survey = json.loads(paths["signal_survey.json"].read_text())
    if survey.get("source_kind") != "native_observed" or not survey.get("governing_signal_id"):
        raise ValueError("Original governing signal survey unverified")
    samples = rows(paths["steady-red-native-samples.jsonl"])
    trace = rows(paths["trace.jsonl"])
    mapping = rows(paths["video_frames.jsonl"])
    if not (len(samples) == len(trace) == len(mapping) == 480):
        raise ValueError("Original 480-frame source count differs")
    for frame, (sample, row, mapped) in enumerate(zip(samples, trace, mapping)):
        if (sample.get("frame") != frame or row.get("frame") != frame
                or mapped.get("carla_frame") != frame
                or sample.get("native_frame") != mapped.get("native_frame")
                or abs(sample.get("time_s", -1) - mapped.get("time_s", -2)) > 1e-6):
            raise ValueError("Original signal/body/video time join differs")
        if sample.get("source_kind") != "native_observed" or sample.get("governing_signal_id") != survey["governing_signal_id"]:
            raise ValueError("Original governing head or source kind differs")
    review = json.loads(source(attempt, args.review).read_text())
    check_review(review, args.case, paths)
    source_receipts = {}
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        video = paths[name + ".mkv"]
        receipt = output.with_name("source-" + name + "-" + args.case.rsplit("__", 1)[-1] + ".json")
        media.audit(video, 480, mapping_sha256=sha(paths["video_frames.jsonl"]), receipt=receipt)
        media.verify_receipt(video, receipt, 480, mapping_sha256=sha(paths["video_frames.jsonl"]))
        source_receipts[name] = {"video_sha256": sha(video), "decode_receipt_sha256": sha(receipt)}
    final = source(attempt, args.video)
    converted_trace = source(attempt, args.trace)
    decode = output.with_name("source-decode-" + args.case.rsplit("__", 1)[-1] + ".json")
    media.audit(final, 480, mapping_sha256=sha(paths["video_frames.jsonl"]), receipt=decode)
    verified = media.verify_receipt(final, decode, 480, mapping_sha256=sha(paths["video_frames.jsonl"]))
    proof = {"format": "worker-delivery-audit", "passed": True, "case_id": args.case,
             "job_id": args.job, "attempt": args.attempt_number, "recording_id": args.recording_id,
             "source_result_sha256": sha(result_path), "frames": 480,
             "video": args.video, "video_sha256": sha(final), "trace": args.trace,
             "trace_sha256": sha(converted_trace), "checks": {key: True for key in CHECKS},
             "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(__file__),
             "source_decode_receipt_path": str(decode), "source_decode_receipt_sha256": sha(decode),
             "source_decode_auditor_sha256": verified["auditor_sha256"],
             "source_video_receipts": source_receipts,
             "independent_review_sha256": sha(source(attempt, args.review))}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case, negative):
    result = {"case_id": case, "provenance_kind": "native", "diagnostic_fixture": False,
              "physical_checks": {"maneuver": {"status": "met"}}, "maneuver_completed": True,
              "accepted": False, "legal_verdict_claimed": False,
              "measured_values": {"first_green_frame": 300},
              "target_checks": [{"measured": 140}]}
    if negative:
        result["provenance_kind"] = "synthetic_fixture"
        check_result(result, case)
        raise AssertionError("Synthetic fixture accepted as original")
    check_result(result, case)
    for key, value in (("diagnostic_fixture", True), ("maneuver_completed", False),
                       ("accepted", True), ("target_checks", [])):
        changed = dict(result, **{key: value})
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Incomplete source or physical state accepted: " + key)
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
    parser.add_argument("--review", default="independent-red-review.json")
    parser.add_argument("--job", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    options = parser.parse_args()
    print(json.dumps(selftest(options.case, options.negative) if options.self_test else audit(options)))

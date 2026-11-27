"""Independent original-source acceptance audit for NRS 484B.267(2)(c).

This audit is run after saved processing. Its CPU self test exercises source
rejection; only an original Native capture and independent review can pass it.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "native"))
from audit_capture import audit as audit_native, exact_request

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join",
          "full_video_decode", "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    if root.resolve() not in path.parents or not path.is_file():
        raise ValueError("Missing original source: " + name)
    return path


def check_result(result, case):
    if result.get("case_id") != case or result.get("provenance_kind") != "original_native":
        raise ValueError("Original Native result unverified")
    values = result.get("measured_values", {})
    if (values.get("source_kind") != "original_native" or values.get("sample_count") != 600
            or values.get("physical_acceptance_claimed") is not False
            or values.get("legal_verdict_claimed") is not False):
        raise ValueError("Original physical travel completion unverified")
    if result.get("accepted") is not False:
        raise ValueError("Source finalizer preaccepted a legal outcome")


def check_review(review, case, sources):
    if (review.get("format") != "c405647-independent-original-review-v1"
            or review.get("case_id") != case or not review.get("reviewer_id")
            or review.get("legal_verdict_claimed") is not False):
        raise ValueError("Independent original review missing")
    for name, path in sources.items():
        if review.get("source_sha256", {}).get(name) != sha(path):
            raise ValueError("Independent original review source changed: " + name)
    for key in ("all_participants_reviewed", "actual_pixels_reviewed",
                "physical_completion_reviewed", "flashing_lights_reviewed",
                "visible_indication_reviewed", "officer_direction_reviewed"):
        if review.get(key) is not True:
            raise ValueError("Independent original review incomplete: " + key)
    frames = review.get("reviewed_frames")
    if (not isinstance(frames, list) or not frames or
            any(type(frame) is not int or frame < 0 or frame >= 600 for frame in frames)
            or not review.get("source_documentation")):
        raise ValueError("Independent original pixel documentation missing")


def audit(args):
    from scenario_pipeline.worker_exchange import media
    attempt = Path(args.attempt).resolve()
    output = Path(args.output).resolve()
    condition = args.case[len(ROOT.name) + 2:]
    if exact_request(condition)["case_id"] != args.case:
        raise ValueError("Unknown exact case")
    result_path = source(attempt, "result.json")
    check_result(json.loads(result_path.read_text()), args.case)
    native = audit_native(attempt, condition)
    names = ("observed-actors.jsonl", "video_frames.jsonl", "emergency_review.json",
             "native-capture-report.json", *(name + ".mkv" for name in VIEWS))
    sources = {name: source(attempt, name) for name in names}
    review = json.loads(source(attempt, args.review).read_text())
    check_review(review, args.case, sources)
    mapping = sha(sources["video_frames.jsonl"])
    decodes = {}
    for name in VIEWS:
        receipt = output.with_name(output.stem + "-" + name + "-decode.json")
        video = sources[name + ".mkv"]
        media.audit(video, 600, mapping_sha256=mapping, receipt=receipt)
        media.verify_receipt(video, receipt, 600, mapping_sha256=mapping)
        decodes[name] = {"video_sha256": sha(video), "decode_receipt_sha256": sha(receipt)}
    proof = {"format": "c405647-independent-delivery-audit-v1", "case_id": args.case,
             "passed": True, "checks": {key: True for key in CHECKS},
             "source_result_sha256": sha(result_path), "native_capture_audit": native,
             "independent_review_sha256": sha(source(attempt, args.review)),
             "source_video_decodes": decodes, "legal_verdict_claimed": False}
    output.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


def selftest(case, negative):
    result = {"case_id": case, "provenance_kind": "original_native", "accepted": False,
              "measured_values": {"source_kind": "original_native", "sample_count": 600,
                                  "physical_acceptance_claimed": False,
                                  "legal_verdict_claimed": False}}
    check_result(result, case)
    for key, value in (("provenance_kind", "synthetic_local_diagnostic"), ("accepted", True)):
        changed = dict(result, **{key: value})
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid original result accepted")
    for value in (0, 599):
        changed = json.loads(json.dumps(result))
        changed["measured_values"]["sample_count"] = value
        try:
            check_result(changed, case)
        except ValueError:
            pass
        else:
            raise AssertionError("Incomplete original frame count accepted")
    if negative:
        result["measured_values"]["sample_count"] = 0
        check_result(result, case)
        raise AssertionError("Missing source accepted")
    return {"case_id": case, "original_source_predicates_tested": True,
            "physical_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", choices=("positive", "negative"))
    parser.add_argument("--attempt")
    parser.add_argument("--output")
    parser.add_argument("--review", default="independent-review.json")
    args = parser.parse_args()
    print(json.dumps(selftest(args.case, args.self_test == "negative") if args.self_test
                     else audit(args), sort_keys=True))

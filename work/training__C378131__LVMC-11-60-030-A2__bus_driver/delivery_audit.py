"""Independent source-bound bus delivery audit and CPU protocol self-test."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

try:
    from analysis.independent_audits import audit_source
    from analysis.saved_only import extract
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from analysis.independent_audits import audit_source
    from analysis.saved_only import extract

HERE = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing delivery source: " + str(path))
    return json.loads(path.read_text())


def source_path(root, relative):
    root = Path(root).resolve()
    result = (root / relative).resolve()
    if root not in result.parents or not result.is_file():
        raise ValueError("Missing delivery source: " + relative)
    return result


def selftest(case, negative=False):
    slug = case.removeprefix(HERE.name + "__")
    source = HERE / "selected-source" / slug
    if not source.is_dir():
        raise ValueError("Unknown exact bus case: " + case)
    with tempfile.TemporaryDirectory(prefix="bus-delivery-test-") as temporary:
        attempt = Path(temporary) / "attempt"
        shutil.copytree(source, attempt)
        if negative:
            (attempt / "bus_context.json").unlink()
        measured = extract(attempt, Path(temporary) / "measurement.json", fixture=True)
        if measured["source_kind"] != "synthetic_native_sample" or measured["physical_completion"] != "unverified":
            raise ValueError("CPU fixture attempted original physical acceptance")
        if measured["stopped_body_in_authored_segment_frames_measured"] < 1:
            raise ValueError("source-bound stopped bus body missing")
        return {"case_id": case, "passed": True, "scope": "synthetic source protocol only",
                "joined_frames": 600, "physical_acceptance_claimed": False}


def audit(case, attempt, processing, review_path, job_id, attempt_number,
          recording_id, output, decode_receipt):
    attempt = Path(attempt).resolve()
    processing_path = Path(processing).resolve()
    review_path = Path(review_path).resolve()
    output = Path(output)
    context = read(attempt / "bus_context.json")
    source = audit_source(attempt, context, fixture=False)
    receipt = read(processing_path)
    result_path = attempt / "result.json"
    result = read(result_path)
    review = read(review_path)
    if (receipt.get("case_id") != case or receipt.get("passed") is not True or
            receipt.get("recorded_only") is not True or receipt.get("missing_evidence") is not False or
            receipt.get("timestamp_joins", {}).get("frames") != 600 or
            receipt.get("originals_preserved") is not True):
        raise ValueError("saved processing source binding missing")
    if (result.get("provenance_kind") != "native" or result.get("diagnostic_fixture") is True or
            context["source_kind"] != "original_native_bus_readback"):
        raise ValueError("original Native source required")
    if (review.get("format") != "bus-independent-original-review-v1" or
            review.get("case_id") != case or review.get("legal_outcome") is not None or
            review.get("source_hashes") != source["source_sha256"]):
        raise ValueError("independent original review identity or source hashes differ")
    for key in ("bus_class_reviewed", "actual_loading_reviewed", "loading_place_reviewed",
                "designation_authority_reviewed", "emergency_reviewed",
                "physical_completion_reviewed"):
        if review.get(key) is not True:
            raise ValueError("independent physical review missing: " + key)
    pixel_boxes = review.get("pixel_boxes", [])
    if {box.get("claim") for box in pixel_boxes} < {"bus", "passenger", "door", "loading_place"}:
        raise ValueError("actual pixel review incomplete")
    for box in pixel_boxes:
        if box.get("camera") not in CAMERAS or not isinstance(box.get("frame"), int) or not 0 <= box["frame"] < 600:
            raise ValueError("invalid actual pixel review box")
        rect = box.get("rect_xywh")
        if not isinstance(rect, list) or len(rect) != 4 or any(type(x) is not int or x < 0 for x in rect) or rect[2] < 1 or rect[3] < 1:
            raise ValueError("invalid actual pixel rectangle")
    video = source_path(attempt, review["video"])
    trace = source_path(attempt, review["trace"])
    mapping = attempt / "video_frames.jsonl"
    scenes = read(trace)["scenes"]
    if len(scenes) != 600:
        raise ValueError("Core scene count differs from Native source")
    frame_rows = [json.loads(line) for line in mapping.read_text().splitlines()]
    if any(row["video_frame"] != index or scenes[index]["t"] != round(row["time_s"] * 1000)
           for index, row in enumerate(frame_rows)):
        raise ValueError("Core and Native time join differs")
    import os
    if not os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT"):
        raise ValueError("Set SCENARIO_PIPELINE_OUTPUT_ROOT before runtime media imports")
    from worker_exchange.media import verify_receipt
    decoded = verify_receipt(video, decode_receipt, 600, mapping_sha256=sha(mapping))
    if review.get("video_sha256") != sha(video) or review.get("trace_sha256") != sha(trace):
        raise ValueError("independent review video or trace hash differs")
    payload = {"format": "worker-delivery-audit", "passed": True, "case_id": case,
               "job_id": job_id, "attempt": attempt_number, "recording_id": recording_id,
               "source_result_sha256": sha(result_path), "frames": 600,
               "video": review["video"], "video_sha256": sha(video),
               "trace": review["trace"], "trace_sha256": sha(trace),
               "checks": {key: True for key in CHECKS},
               "auditor_path": str(Path(__file__).resolve()), "auditor_sha256": sha(__file__),
               "source_decode_receipt_path": str(Path(decode_receipt).resolve()),
               "source_decode_receipt_sha256": sha(decode_receipt),
               "source_decode_auditor_sha256": decoded["auditor_sha256"],
               "review_sha256": sha(review_path), "physical_acceptance_claimed": False,
               "legal_verdict": None}
    output.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-selftest", action="store_true")
    for name in ("attempt", "processing", "review", "job-id", "recording-id", "output",
                 "source-decode-receipt"):
        parser.add_argument("--" + name)
    parser.add_argument("--attempt-number", type=int)
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.case, negative=args.negative_selftest)))
    else:
        print(json.dumps(audit(args.case, args.attempt, args.processing, args.review,
                               args.job_id, args.attempt_number, args.recording_id,
                               args.output, args.source_decode_receipt)))


if __name__ == "__main__":
    main()

"""Proposed independent C111662 original delivery audit.

Copy this file into the local batch's state/operations/worker_exchange directory
before canonical acceptance. The audit requires original Native sources, a
source-hashed visual review, Core trace and a full decode of the promoted video.
CPU selftests exercise mechanics only and never produce an accepted recording.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REVIEW_FLAGS = ("vehicle_and_centerline_visible", "turn_path_visible",
                "intersection_extent_reviewed", "district_designation_reviewed",
                "divided_highway_exception_reviewed", "building_use_reviewed")
PIXEL_CLAIMS = ("vehicle", "turn_path", "road_reference", "frontage")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file(), "Missing delivery source: " + str(path))
    return json.loads(path.read_text())


def within(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path != root and root in path.parents and path.is_file(),
            "Delivery source escapes or is missing: " + str(relative))
    return path


def native_modules(bundle):
    native = Path(bundle) / "work/training__C111662__NRS-484B-403-3__motor_vehicle_driver/native"
    require(native.is_dir(), "Selected Native processor missing")
    sys.path.insert(0, str(native))
    from process_original import process as intersection
    from process_original_divided import process as divided
    from audit_frontage_original import audit as frontage
    return intersection, divided, frontage


def media_module():
    from worker_exchange import media
    return media


def check_core_join(attempt, trace):
    scenes = read(trace).get("scenes")
    require(isinstance(scenes, list) and len(scenes) == 800,
            "Core trace lacks 800 original scenes")
    rows = [json.loads(line) for line in (Path(attempt) / "video_frames.jsonl").read_text().splitlines()]
    require(len(rows) == len(scenes), "Original frame map/Core length differs")
    previous = None
    for index, (frame, scene) in enumerate(zip(rows, scenes)):
        t = frame.get("time_s")
        require(frame.get("video_frame") == index and
                type(frame.get("native_frame")) is int and
                type(t) in (int, float) and
                type(scene.get("t")) is int and scene["t"] == round(t * 1000),
                "Original frame/Core timestamp join differs")
        if previous is not None:
            require(frame["native_frame"] == previous + 1,
                    "Original Native frame sequence differs")
        previous = frame["native_frame"]
    return rows


def pixel_checker(review, expected_frames):
    boxes = review.get("pixel_boxes")
    require(isinstance(boxes, list) and len(boxes) >= len(PIXEL_CLAIMS),
            "Independent visual review lacks pixel boxes")
    require(set(item.get("claim") for item in boxes) >= set(PIXEL_CLAIMS),
            "Independent visual review omits a visible feature")
    seen = set()
    by_frame = {}
    for item in boxes:
        index = item.get("frame")
        rect = item.get("rect_xywh")
        require(type(index) is int and 0 <= index < expected_frames and
                isinstance(rect, list) and len(rect) == 4 and
                all(type(value) is int for value in rect) and
                rect[2] >= 2 and rect[3] >= 2,
                "Invalid reviewed pixel box")
        by_frame.setdefault(index, []).append(item)

    def check(frame):
        for item in by_frame.get(frame.index, []):
            x, y, width, height = item["rect_xywh"]
            require(x >= 0 and y >= 0 and x + width <= frame.width and
                    y + height <= frame.height, "Reviewed pixel box exceeds decoded video")
            # This proves that the cited pixels exist and vary. The independent
            # reviewer, not this contrast check, identifies the claimed feature.
            values = []
            for row in range(y, y + height):
                start = (row * frame.width + x) * 3
                values.extend(frame.pixels[start:start + width * 3])
            require(max(values) > min(values), "Reviewed pixel box is flat")
            seen.add(item["claim"])

    return check, seen


def check_review(review, attempt, video):
    require(review.get("source_kind") == "original_native_review" and
            isinstance(review.get("reviewer_id"), str) and review["reviewer_id"].strip() and
            all(review.get(name) is True for name in REVIEW_FLAGS),
            "Independent original visual review incomplete")
    require(review.get("primary_video_sha256") == sha(video) and
            review.get("video_frames_sha256") == sha(Path(attempt) / "video_frames.jsonl") and
            review.get("raw_sha256") == sha(Path(attempt) / "native-raw-actors.jsonl"),
            "Independent visual review source hashes differ")
    media = review.get("media_sha256")
    require(isinstance(media, dict) and set(media) == {name + ".mkv" for name in CAMERAS}
            and all(media[name + ".mkv"] == sha(Path(attempt) / (name + ".mkv"))
                    for name in CAMERAS),
            "Four-camera visual review hashes differ")
    source_refs = review.get("district_and_building_use_sources")
    require(isinstance(source_refs, list) and source_refs and
            all(isinstance(row, dict) and row.get("path") and row.get("sha256") and
                sha(within(attempt, row["path"])) == row["sha256"] for row in source_refs),
            "District/building-use review lacks retained sources")


def audit(case, job_id, attempt_number, recording_id, bundle, attempt, review_path,
          video_name, trace_name, decode_receipt, output):
    attempt, bundle, output = Path(attempt).resolve(), Path(bundle).resolve(), Path(output).resolve()
    require(type(job_id) is int and job_id > 0 and type(attempt_number) is int and attempt_number > 0,
            "Canonical job or attempt identity invalid")
    require(attempt.parent.name == recording_id and attempt in output.parents,
            "Audit output is outside exact recording attempt")
    video, trace = within(attempt, video_name), within(attempt, trace_name)
    result_path = within(attempt, "result.json")
    review = read(review_path)
    config = read(bundle / "config.json")
    require(config["case_id"] == case and review.get("case_id") == case and
            review.get("candidate_id") == config["candidate_id"],
            "Delivery case or candidate identity differs")
    check_review(review, attempt, video)
    intersection, divided, frontage_audit = native_modules(bundle)
    processor = divided if case.endswith(("__divided_reference", "__divided_opening")) else intersection
    measured = processor(bundle, attempt, review_path)
    frontage = frontage_audit(bundle, attempt)
    require(measured.get("original_native_observed") is True and
            measured.get("frames_joined") == 800 and
            measured.get("observed_heading_change_deg", 0) >= 150 and
            frontage.get("passed") is True and
            frontage.get("case_id") == case and
            measured.get("legal_verdict") is None,
            "Original physical completion or frontage evidence incomplete")
    rows = check_core_join(attempt, trace)
    callback, seen = pixel_checker(review, len(rows))
    media = media_module()
    receipt_path = Path(decode_receipt).resolve()
    require(receipt_path.parent != attempt and not receipt_path.exists(),
            "Use a fresh operations-owned full-decode receipt")
    decoded = media.audit(video, len(rows), checkers={"c111662_reviewed_pixels":
                          (sha(Path(__file__)), callback)},
                          mapping_sha256=sha(attempt / "video_frames.jsonl"),
                          receipt=receipt_path)
    require(seen >= set(PIXEL_CLAIMS) and decoded.get("passed") is True,
            "Reviewed original pixels did not decode")
    value = {"format": "worker-delivery-audit", "passed": True,
             "case_id": case, "job_id": job_id, "attempt": attempt_number,
             "recording_id": recording_id, "source_result_sha256": sha(result_path),
             "video": str(video.relative_to(attempt)), "video_sha256": sha(video),
             "trace": str(trace.relative_to(attempt)), "trace_sha256": sha(trace),
             "frames": len(rows), "checks": {name: True for name in CHECKS},
             "auditor_path": str(Path(__file__).resolve()),
             "auditor_sha256": sha(Path(__file__)),
             "source_decode_receipt_path": str(receipt_path),
             "source_decode_receipt_sha256": sha(receipt_path),
             "source_decode_auditor_sha256": decoded["auditor_sha256"],
             "original_measurement": measured,
             "frontage_measurement": frontage,
             "visual_review_sha256": sha(review_path),
             "legal_verdict": None}
    output.write_text(json.dumps(value, indent=2) + "\n")
    return value


def selftest(case, negative=False):
    from types import SimpleNamespace
    require(case.endswith(("__reference", "__contrast", "__divided_reference", "__divided_opening")),
            "Unknown exact C111662 case")
    frame = SimpleNamespace(index=0, width=3, height=3,
                            pixels=bytes([0, 20, 40, 60, 80, 100, 120, 140, 160] * 3))
    review = {"pixel_boxes": [{"claim": name, "frame": 0, "rect_xywh": [0, 0, 2, 2]}
                              for name in PIXEL_CLAIMS]}
    if negative:
        review["pixel_boxes"][0]["rect_xywh"] = [10, 10, 2, 2]
    callback, seen = pixel_checker(review, 1)
    callback(frame)
    require(seen == set(PIXEL_CLAIMS), "Pixel selftest did not exercise all claims")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        mapping = root / "video_frames.jsonl"
        mapping.write_text("".join(json.dumps({"video_frame": index,
                                               "native_frame": 1000 + index,
                                               "time_s": (index + 1) / 20}) + "\n"
                                   for index in range(800)))
        trace = root / "trace.json"
        trace.write_text(json.dumps({"scenes": [{"t": round((index + 1) * 50)}
                                                 for index in range(800)]}))
        require(len(check_core_join(root, trace)) == 800,
                "Original frame/Core selftest failed")
        altered = json.loads(trace.read_text())
        altered["scenes"][400]["t"] += 1
        trace.write_text(json.dumps(altered))
        try:
            check_core_join(root, trace)
        except ValueError:
            pass
        else:
            raise ValueError("Changed Core timestamp was accepted")
        try:
            within(root, "../escape.json")
        except ValueError:
            pass
        else:
            raise ValueError("Escaping delivery source was accepted")
    return {"format": "c111662-delivery-auditor-selftest-v1", "case_id": case,
            "passed": True, "internal_negative_checks": 2,
            "synthetic_fixture_only": True,
            "original_native_observed": False, "accepted": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--selftest", action="store_true")
    parser.add_argument("--negative-selftest", action="store_true")
    parser.add_argument("--job-id", type=int)
    parser.add_argument("--attempt-number", type=int)
    parser.add_argument("--recording-id")
    parser.add_argument("--bundle")
    parser.add_argument("--attempt-dir")
    parser.add_argument("--review")
    parser.add_argument("--video")
    parser.add_argument("--trace")
    parser.add_argument("--decode-receipt")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.case, negative=args.negative_selftest)))
    else:
        required = (args.job_id, args.attempt_number, args.recording_id, args.bundle,
                    args.attempt_dir, args.review, args.video, args.trace,
                    args.decode_receipt, args.output)
        if any(value is None for value in required):
            parser.error("Original delivery audit requires all source and output arguments")
        print(json.dumps(audit(args.case, args.job_id, args.attempt_number,
                               args.recording_id, args.bundle, args.attempt_dir,
                               args.review, args.video, args.trace,
                               args.decode_receipt, args.output)))

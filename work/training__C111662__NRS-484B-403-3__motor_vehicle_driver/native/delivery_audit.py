"""Proposed independent C111662 original delivery audit.

Copy this file into the local batch's state/operations/worker_exchange directory
before canonical acceptance. The audit requires original Native sources, a
source-hashed visual review, Core trace and a full decode of the promoted video.
CPU selftests exercise mechanics only and never produce an accepted recording.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import subprocess

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
INTERSECTION_FLAGS = ("vehicle_and_centerline_visible", "turn_path_visible",
                      "intersection_extent_reviewed", "district_designation_reviewed",
                      "divided_highway_exception_reviewed")
DIVIDED_FLAGS = ("vehicle_and_median_visible", "turn_path_visible",
                 "opening_extent_reviewed", "district_designation_reviewed",
                 "appropriate_crossing_place_reviewed")
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


def native_processor(bundle, case):
    native = Path(bundle) / "work/training__C111662__NRS-484B-403-3__motor_vehicle_driver/native"
    require(native.is_dir(), "Selected Native processor missing")
    sys.path.insert(0, str(native))
    if case.endswith(("__divided_reference", "__divided_opening")):
        from process_original_divided import process
    else:
        from process_original import process
    return process


def frontage_audit(bundle, attempt, case):
    bundle, attempt = Path(bundle), Path(attempt)
    plan = read(bundle / "frontage-plan.json")
    readback = read(attempt / "native-frontage-readback.json")
    mapping = read(attempt / "native-map-readback.json")
    capture = read(attempt / "native-capture-report.json")
    require(plan.get("format") == "c111662-authored-frontage-plan-v1" and
            plan.get("minimum_frontage_ft") == 300 and
            plan.get("maximum_window_ft") == 600 and
            plan.get("district_designation_verified") is False and
            plan.get("legal_verdict") is None,
            "Authored frontage plan changed or claims legal designation")
    stations, segments = plan.get("station_x_m"), plan.get("segments_x_m")
    require(isinstance(stations, list) and isinstance(segments, list) and
            len(segments) == 2 and all(isinstance(row, list) and len(row) == 2
                                       and all(type(v) in (int, float) and math.isfinite(v) for v in row)
                                       for row in segments),
            "Authored frontage stations or segments missing")
    require(readback.get("format") == "c111662-native-frontage-readback-v1" and
            readback.get("source_kind") == "original_native_geometry" and
            readback.get("district_designation_verified") is False and
            readback.get("building_use_legally_verified") is False and
            readback.get("legal_verdict") is None,
            "Original frontage readback provenance or legal claim differs")
    blueprint = str(readback.get("blueprint_id", "")).lower()
    require(blueprint.startswith("static.prop.") and
            any(token in blueprint for token in ("building", "shop", "store", "cafe")),
            "Frontage prop has no building-use asset identity")
    ids, intervals = readback.get("actor_ids"), readback.get("native_actor_intervals_x_m")
    require(isinstance(ids, list) and len(ids) == len(stations) and
            len(set(ids)) == len(ids) and all(type(v) is int for v in ids) and
            isinstance(intervals, list) and len(intervals) == len(stations),
            "Original frontage actor inventory incomplete")
    for station, interval in zip(stations, intervals):
        require(isinstance(interval, list) and len(interval) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in interval) and
                type(station) in (int, float) and interval[0] <= station <= interval[1],
                "Native frontage interval misses authored station")
    measured = 0.0
    for lo, hi in segments:
        clipped = sorted((max(a, lo), min(b, hi)) for a, b in intervals if min(b, hi) > max(a, lo))
        end = -math.inf
        for a, b in clipped:
            measured += max(0.0, b - max(a, end))
            end = max(end, b)
    require(measured * 3.280839895013123 + 1e-8 >= 300 and
            abs(measured - readback.get("native_frontage_m", -1)) <= 1e-6,
            "Measured Native building frontage is short or inconsistent")
    road = ("divided-highway.xodr" if case.endswith(("__divided_reference", "__divided_opening"))
            else "district-crossroads.xodr")
    require(mapping.get("source_kind") == "original_native" and
            mapping.get("road_sha256") == sha(bundle / road) and
            mapping.get("ego_actor_id") not in ids and
            capture.get("error") is None and capture.get("observed_frames") == 800,
            "Original map, frontage actor or capture source differs")
    return {"passed": True, "case_id": capture.get("case_id"),
            "candidate_id": capture.get("candidate_id"),
            "native_frontage_m": measured,
            "district_designation_verified": False,
            "building_use_legally_verified": False,
            "legal_verdict": None,
            "sources": {name: sha(path) for name, path in (
                ("frontage-plan.json", bundle / "frontage-plan.json"),
                ("native-frontage-readback.json", attempt / "native-frontage-readback.json"),
                ("native-map-readback.json", attempt / "native-map-readback.json"),
                ("native-capture-report.json", attempt / "native-capture-report.json"),
                (road, bundle / road))}}


def media_module():
    for parent in Path(__file__).resolve().parents:
        exported = parent / "runtime/pipeline/scenario_pipeline/worker_exchange/media.py"
        if exported.is_file():
            sys.path.insert(0, str(exported.parent.parent))
            break
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
    distinct = set()
    for item in boxes:
        index = item.get("frame")
        rect = item.get("rect_xywh")
        require(type(index) is int and 0 <= index < expected_frames and
                isinstance(rect, list) and len(rect) == 4 and
                all(type(value) is int for value in rect) and
                rect[2] >= 2 and rect[3] >= 2,
                "Invalid reviewed pixel box")
        key = (index, tuple(rect))
        require(key not in distinct, "Distinct visible claims reuse a reviewed pixel box")
        distinct.add(key)
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


def check_review(review, attempt, video, case):
    divided = case.endswith(("__divided_reference", "__divided_opening"))
    flags = DIVIDED_FLAGS if divided else INTERSECTION_FLAGS
    require(review.get("source_kind") == "original_native_review" and
            isinstance(review.get("reviewer_id"), str) and review["reviewer_id"].strip() and
            all(review.get(name) is True for name in flags) and
            review.get("building_use_reviewed") is True,
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
    check_review(review, attempt, video, case)
    processor = native_processor(bundle, case)
    measured = processor(bundle, attempt, review_path)
    frontage = frontage_audit(bundle, attempt, case)
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
    review = {"pixel_boxes": [{"claim": name, "frame": 0,
                               "rect_xywh": [index % 2, index // 2, 2, 2]}
                              for index, name in enumerate(PIXEL_CLAIMS)]}
    if negative:
        review["pixel_boxes"][0]["rect_xywh"] = [10, 10, 2, 2]
    callback, seen = pixel_checker(review, 1)
    callback(frame)
    require(seen == set(PIXEL_CLAIMS), "Pixel selftest did not exercise all claims")
    repeated = {"pixel_boxes": [dict(item) for item in review["pixel_boxes"]]}
    repeated["pixel_boxes"][1]["rect_xywh"] = repeated["pixel_boxes"][0]["rect_xywh"]
    try:
        pixel_checker(repeated, 1)
    except ValueError:
        pass
    else:
        raise ValueError("Reused visual claim box was accepted")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        video = root / "tiny.mkv"
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "rawvideo", "-pixel_format", "rgb24", "-video_size", "3x3",
                        "-framerate", "20", "-i", "pipe:0", "-frames:v", "1",
                        "-c:v", "ffv1", str(video)],
                       input=frame.pixels, check=True)
        receipt = root / "decode.json"
        media = media_module()
        callback, decoded_claims = pixel_checker(review, 1)
        decoded = media.audit(video, 1, checkers={"c111662_reviewed_pixels":
                              (sha(Path(__file__)), callback)},
                              mapping_sha256="fixture-map", receipt=receipt)
        require(decoded.get("passed") is True and
                decoded_claims == set(PIXEL_CLAIMS) and
                media.verify_receipt(video, receipt, 1,
                                     mapping_sha256="fixture-map")["passed"] is True,
                "Full FFV1 decode selftest failed")
        try:
            media.verify_receipt(video, receipt, 1, mapping_sha256="altered-map")
        except ValueError:
            pass
        else:
            raise ValueError("Stale decoded mapping was accepted")
        (root / "native-raw-actors.jsonl").write_text("fixture actor\n")
        (root / "video_frames.jsonl").write_text("fixture frame\n")
        camera_hashes = {}
        for name in CAMERAS:
            camera = root / (name + ".mkv")
            camera.write_bytes(b"synthetic camera marker: " + name.encode())
            camera_hashes[camera.name] = sha(camera)
        source = root / "district-and-building-use.txt"
        source.write_text("Synthetic review source; no legal designation.\n")
        flags = DIVIDED_FLAGS if case.endswith(("__divided_reference", "__divided_opening")) else INTERSECTION_FLAGS
        source_review = {"source_kind": "original_native_review", "reviewer_id": "cpu-fixture",
                         "primary_video_sha256": sha(video),
                         "video_frames_sha256": sha(root / "video_frames.jsonl"),
                         "raw_sha256": sha(root / "native-raw-actors.jsonl"),
                         "media_sha256": camera_hashes,
                         "district_and_building_use_sources": [{"path": source.name,
                                                                 "sha256": sha(source)}],
                         "building_use_reviewed": True,
                         **{flag: True for flag in flags}}
        check_review(source_review, root, video, case)
        source_review[flags[0]] = False
        try:
            check_review(source_review, root, video, case)
        except ValueError:
            pass
        else:
            raise ValueError("Missing branch visual review was accepted")
        source_review[flags[0]] = True
        source_review["media_sha256"]["overview.mkv"] = "0" * 64
        try:
            check_review(source_review, root, video, case)
        except ValueError:
            pass
        else:
            raise ValueError("Changed source camera was accepted")
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
        bundle = root / "bundle"
        capture = root / "capture"
        bundle.mkdir()
        capture.mkdir()
        road = ("divided-highway.xodr" if case.endswith(("__divided_reference", "__divided_opening"))
                else "district-crossroads.xodr")
        (bundle / road).write_text("synthetic road fixture\n")
        stations = [-72.5 + 5 * i for i in range(10)] + [27.5 + 5 * i for i in range(10)]
        plan = {"format": "c111662-authored-frontage-plan-v1",
                "minimum_frontage_ft": 300, "maximum_window_ft": 600,
                "district_designation_verified": False, "legal_verdict": None,
                "station_x_m": stations, "segments_x_m": [[-75, -25], [25, 75]]}
        (bundle / "frontage-plan.json").write_text(json.dumps(plan))
        front = {"format": "c111662-native-frontage-readback-v1",
                 "source_kind": "original_native_geometry", "blueprint_id": "static.prop.building",
                 "actor_ids": list(range(20)),
                 "native_actor_intervals_x_m": [[s - 2.5, s + 2.5] for s in stations],
                 "native_frontage_m": 100,
                 "district_designation_verified": False,
                 "building_use_legally_verified": False, "legal_verdict": None}
        front_path = capture / "native-frontage-readback.json"
        front_path.write_text(json.dumps(front))
        mapping = {"source_kind": "original_native", "road_sha256": sha(bundle / road),
                   "ego_actor_id": 100}
        map_path = capture / "native-map-readback.json"
        map_path.write_text(json.dumps(mapping))
        (capture / "native-capture-report.json").write_text(json.dumps({"error": None,
            "observed_frames": 800, "case_id": case, "candidate_id": "primary"}))
        require(frontage_audit(bundle, capture, case)["native_frontage_m"] == 100,
                "Source-bound frontage fixture failed")
        front["native_actor_intervals_x_m"] = [[s - 2, s + 2] for s in stations]
        front["native_frontage_m"] = 80
        front_path.write_text(json.dumps(front))
        try:
            frontage_audit(bundle, capture, case)
        except ValueError:
            pass
        else:
            raise ValueError("Short Native frontage was accepted")
        front["native_actor_intervals_x_m"] = [[s - 2.5, s + 2.5] for s in stations]
        front["native_frontage_m"] = 100
        front_path.write_text(json.dumps(front))
        mapping["road_sha256"] = "0" * 64
        map_path.write_text(json.dumps(mapping))
        try:
            frontage_audit(bundle, capture, case)
        except ValueError:
            pass
        else:
            raise ValueError("Changed Native road was accepted")
    return {"format": "c111662-delivery-auditor-selftest-v1", "case_id": case,
            "passed": True, "internal_negative_checks": 8,
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

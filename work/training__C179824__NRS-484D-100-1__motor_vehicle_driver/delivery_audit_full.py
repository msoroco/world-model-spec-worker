"""Independent original-source delivery audit for the selected NRS 484D.100(1) cases.

The self-test checks predicates only. A delivery audit requires original Native
result/video, an independent review tied to their hashes, and full video decode.
"""
import argparse
import hashlib
import json
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
CHECKS = ("native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = (root / name).resolve()
    require(root == path or root in path.parents, "Source escapes original attempt: " + name)
    require(path.is_file(), "Missing original source: " + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_result(result, case):
    require(result.get("case_id") == case and result.get("provenance_kind") == "native_saved_sample"
            and result.get("diagnostic_fixture") is False,
            "Missing original source: exact Native result")
    require(result.get("accepted") is False and result.get("legal_verdict_claimed") is False,
            "Finalizer preaccepted legal or physical outcome")
    require(set(result.get("video_references", [])) == {camera + ".mkv" for camera in CAMERAS},
            "Four original video references missing")
    require(result.get("maneuver_completed") is True and
            result.get("physical_checks", {}).get("maneuver", {}).get("status") == "met",
            "Original physical maneuver incomplete")
    require(result.get("recording_evidence") and result.get("trace_reference") and
            result.get("video_frame_map_reference"), "Original evidence references missing")
    require(result.get("measured_values", {}).get("legal_verdict_claimed") is False,
            "Measured report claimed a legal verdict")
    return result


def check_frames(frame_rows, result):
    require(len(frame_rows) == 600, "Original frame count differs from 600")
    for i, row in enumerate(frame_rows):
        require(row.get("video_frame") == i and
                set(row.get("camera_native_frames", {})) == set(CAMERAS) and
                isinstance(row.get("time_s"), (float, int)),
                "Original four-view frame join failed")
    return len(frame_rows)


def check_review(review, case, hashes):
    require(review.get("format") == "c179824-original-full-law-review-v1" and
            review.get("source_kind") == "original_native_review" and
            review.get("case_id") == case and review.get("reviewer_id"),
            "Missing independent original full-law review")
    for key, digest in hashes.items():
        require(review.get(key) == digest, "Original source review hash changed: " + key)
    require(review.get("reviewed_frames") and
            set(review.get("reviewed_cameras", [])) == set(CAMERAS),
            "Original pixel review lacks all cameras")
    require(review.get("person_discernibility_at_1000ft") in (True, False) and
            review.get("vehicle_discernibility_at_1000ft") in (True, False),
            "Person and vehicle discernibility require separate original pixel review")
    require(review.get("civil_sun_event_source_verified") is True and
            review.get("timezone_and_location_verified") is True and
            review.get("public_highway_source_verified") is True,
            "Civil time or Nevada highway source review missing")
    require(review.get("class_equipment_status") in ("met", "not_met") and
            review.get("class_law_source_sha256") and review.get("class_pixel_source_sha256"),
            "Class-specific lamp sufficiency needs law and independent original pixels")
    if case.endswith(("__controlled_1", "__controlled_2")):
        require(review.get("official_device_source_verified") is True,
                "Official device authority source review missing")
    if case.endswith(("__parked_lamps_1", "__parked_lamps_2")):
        require(review.get("parked_exception_status") in ("applies", "does_not_apply") and
                review.get("nrs_484d_165_source_sha256") and
                review.get("shoulder_and_stopped_source_sha256"),
                "Parked exception source and physical state review missing")
    require(review.get("legal_verdict_claimed") is False,
            "Independent review claimed a legal verdict")
    return review


def audit(args):
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "runtime" / "scenario_pipeline"))
    from worker_exchange import media
    from class_lamp_measure import measure as measure_class_lamps
    attempt = Path(args.attempt).resolve()
    result_path = source(attempt, "result.json")
    result = check_result(json.loads(result_path.read_text()), args.case)
    map_path = source(attempt, result["video_frame_map_reference"])
    count = check_frames(rows(map_path), result)
    source(attempt, result["trace_reference"])
    for evidence in result["recording_evidence"]:
        source(attempt, evidence["reference"])
    hashes = {"result_sha256": sha(result_path), "frame_map_sha256": sha(map_path)}
    videos = {}
    for camera in CAMERAS:
        path = source(attempt, camera + ".mkv")
        videos[camera] = path
        hashes[camera + "_video_sha256"] = sha(path)
    review_path = source(attempt, args.review)
    review = check_review(json.loads(review_path.read_text()), args.case, hashes)
    class_review_path = source(attempt, "class-lamp-review.json")
    class_law_path = source(attempt, "chapter-484d-source.txt")
    geometry_path = source(attempt, "road.xodr")
    class_report = measure_class_lamps(class_review_path.read_bytes(),
                                       videos["driver_reference"].read_bytes(),
                                       geometry_path.read_bytes(), class_law_path.read_bytes())
    require(review["class_law_source_sha256"] == sha(class_law_path) and
            review["class_pixel_source_sha256"] == sha(class_review_path),
            "Class-specific lamp source review hash changed")
    fields = class_report["measurements"]
    if review["class_equipment_status"] == "met":
        require(all(value for key, value in fields.items() if key != "front_height_inches"),
                "Class-specific equipment status contradicts original pixel findings")
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for camera, video in videos.items():
        receipt = output.with_name(output.stem + "-" + camera + "-decode.json")
        media.audit(video, count, mapping_sha256=sha(map_path), receipt=receipt)
        media.verify_receipt(video, receipt, count, mapping_sha256=sha(map_path))
        receipts[camera] = {"path": str(receipt), "sha256": sha(receipt)}
    payload = {"format": "worker-delivery-audit", "passed": True, "case_id": args.case,
               "source_result_sha256": sha(result_path), "review_sha256": sha(review_path),
               "frame_count": count, "decoded_cameras": receipts,
               "class_measurement_source_hashes": class_report["source_hashes"],
               "checks": {key: True for key in CHECKS},
               "legal_verdict_claimed": False}
    output.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def self_test(case, negative):
    from class_lamp_measure import self_test as class_self_test
    class_self_test(False)
    try:
        class_self_test(True)
    except ValueError as error:
        require("Original class-specific source review" in str(error),
                "Class-specific missing-law rejection changed")
    else:
        raise AssertionError("Missing class law source passed")
    hashes = {key: hashlib.sha256(key.encode()).hexdigest() for key in
              ("result_sha256", "frame_map_sha256", *(camera + "_video_sha256" for camera in CAMERAS))}
    review = {"format": "c179824-original-full-law-review-v1", "source_kind": "original_native_review",
              "case_id": case, "reviewer_id": "cpu-predicate-fixture", "reviewed_frames": [200, 300, 400],
              "reviewed_cameras": list(CAMERAS), "person_discernibility_at_1000ft": True,
              "vehicle_discernibility_at_1000ft": False, "civil_sun_event_source_verified": True,
              "timezone_and_location_verified": True, "public_highway_source_verified": True,
              "class_equipment_status": "met", "class_law_source_sha256": "source-bound-diagnostic",
              "class_pixel_source_sha256": "source-bound-diagnostic", "official_device_source_verified": True,
              "parked_exception_status": "does_not_apply", "nrs_484d_165_source_sha256": "source-bound-diagnostic",
              "shoulder_and_stopped_source_sha256": "source-bound-diagnostic",
              "legal_verdict_claimed": False, **hashes}
    if negative:
        review.pop("person_discernibility_at_1000ft")
        check_review(review, case, hashes)
        raise AssertionError("Missing original person pixel review passed")
    check_review(review, case, hashes)
    for missing in ("class_law_source_sha256", "overview_video_sha256"):
        damaged = dict(review)
        damaged.pop(missing)
        try:
            check_review(damaged, case, hashes)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing original source passed: " + missing)
    synthetic = {"case_id": case, "provenance_kind": "synthetic_diagnostic", "diagnostic_fixture": True}
    try:
        check_result(synthetic, case)
    except ValueError:
        pass
    else:
        raise AssertionError("Synthetic result passed original source gate")
    return {"case_id": case, "source_predicates_tested": True, "original_capture_attested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--output")
    parser.add_argument("--review", default="original-full-law-review.json")
    args = parser.parse_args()
    print(json.dumps(self_test(args.case, args.negative) if args.self_test else audit(args), indent=2))

"""Original-source comparison audit for the five selected NRS 484D.100(1) comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(comparison, samples):
    members = comparison["case_ids"]
    require([sample.get("case_id") for sample in samples] == members,
            "Exact comparison case order changed")
    require(all(sample.get("source_kind") == "native_saved_sample" and
                sample.get("original_review_sha256") for sample in samples),
            "Original source-reviewed comparison samples required")
    require(all(sample.get("frame_count") == 600 and sample.get("four_camera_join") is True
                for sample in samples), "Comparison requires four-view 600-frame joins")
    fixed = samples[0].get("fixed_sources", {})
    require(fixed and all(sample.get("fixed_sources") == fixed for sample in samples),
            "Comparison fixed source identity changed")
    key = comparison["deliberate_differences"][0]
    values = [sample.get("variable", {}).get(key) for sample in samples]
    require(all(value is not None for value in values) and len(set(values)) == len(values),
            "Comparison variable did not separate")
    if "minutes_after_sunset" in key or "minutes_before_sunrise" in key:
        require(values == [29, 30, 31], "Civil-time boundary is not below/at/above 30 minutes")
    elif "target_reference_distance_ft" in key:
        require(values == [999, 1000, 1001], "Distance boundary is not below/at/above 1000 feet")
    elif key in ("lamp state under governing official device", "requested_lamp_setting_on"):
        require(values == [True, False], "Lamp comparison does not isolate on/off")
    require(all(sample.get("legal_verdict_claimed") is False for sample in samples),
            "Comparison preclaimed legal verdict")
    return {"comparison_id": comparison["comparison_id"], "case_ids": members,
            "fixed_source_keys": sorted(fixed), "variable": key, "values": values,
            "legal_verdict_claimed": False}


def original_sample(case, attempt):
    from delivery_audit_full import check_result, check_review, check_frames, rows
    attempt = Path(attempt).resolve()
    result_path = attempt / "result.json"
    review_path = attempt / "original-full-law-review.json"
    require(result_path.is_file() and review_path.is_file(), "Missing original comparison result/review")
    result = json.loads(result_path.read_text())
    review = json.loads(review_path.read_text())
    check_result(result, case)
    frame_path = attempt / result["video_frame_map_reference"]
    require(frame_path.is_file() and review.get("frame_map_sha256") == sha(frame_path),
            "Changed original frame-map review")
    check_frames(rows(frame_path), result)
    hashes = {"result_sha256": sha(result_path), "frame_map_sha256": sha(frame_path)}
    for camera in ("overview", "approach", "reference_corner", "driver_reference"):
        video = attempt / (camera + ".mkv")
        require(video.is_file(), "Missing original comparison video: " + camera)
        hashes[camera + "_video_sha256"] = sha(video)
    check_review(review, case, hashes)
    return {"case_id": case, "source_kind": "native_saved_sample",
            "original_review_sha256": sha(review_path), "frame_count": 600,
            "four_camera_join": set(result.get("video_references", [])) ==
            {camera + ".mkv" for camera in ("overview", "approach", "reference_corner", "driver_reference")},
            "fixed_sources": review.get("comparison_fixed_sources", {}),
            "variable": review.get("comparison_variable", {}),
            "legal_verdict_claimed": review.get("legal_verdict_claimed")}


def self_test(comparison, negative):
    key = comparison["deliberate_differences"][0]
    if "minutes" in key:
        values = [29, 30, 31]
    elif "distance" in key:
        values = [999, 1000, 1001]
    else:
        values = [True, False]
    common = {"source_kind": "native_saved_sample", "original_review_sha256": "cpu-predicate-fixture",
              "frame_count": 600, "four_camera_join": True,
              "fixed_sources": {"road": "shared-source-sha", "class": "shared-class-law-sha",
                                "camera": "four-view-20hz", "sun_event": "shared-sun-event-sha"},
              "legal_verdict_claimed": False}
    samples = [dict(common, case_id=case, variable={key: value}) for case, value in
               zip(comparison["case_ids"], values)]
    if negative:
        samples[-1]["fixed_sources"] = dict(common["fixed_sources"], road="another-source-sha")
        compare(comparison, samples)
        raise AssertionError("Changed fixed road source passed")
    proof = compare(comparison, samples)
    damaged = [dict(sample) for sample in samples]
    damaged[-1]["variable"] = {key: values[0]}
    try:
        compare(comparison, damaged)
    except ValueError:
        pass
    else:
        raise AssertionError("Unseparated variable passed")
    return dict(proof, original_capture_attested=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison-id", required=True)
    parser.add_argument("--attempt", action="append", default=[])
    parser.add_argument("--output")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    comparison = next((c for c in PLAN["comparisons"] if c["comparison_id"] == args.comparison_id), None)
    require(comparison is not None, "Unknown exact comparison")
    if args.self_test:
        print(json.dumps(self_test(comparison, args.negative), indent=2))
    else:
        require(len(args.attempt) == len(comparison["case_ids"]), "One original attempt per case required")
        proof = compare(comparison, [original_sample(case, attempt) for case, attempt in
                                     zip(comparison["case_ids"], args.attempt)])
        require(args.output, "Comparison output required")
        Path(args.output).write_text(json.dumps(proof, indent=2) + "\n")
        print(json.dumps(proof, indent=2))

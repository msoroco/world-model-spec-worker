"""Independent read-only original-source audit for C378809 local delivery."""
import argparse
import hashlib
import json
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
REQUIRED = ("trace.jsonl", "video_frames.jsonl", "alley-native.jsonl",
            "capture/evidence.jsonl", "capture/manifest.json", "site-survey.json",
            "goods-review.json") + tuple(name + ".mkv" for name in CAMERAS)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    require(path.is_file(), "Missing original source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    require(path.is_file(), "Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(case_id, attempt, saved, owner_path, pixel_review_path):
    attempt, saved = Path(attempt).resolve(), Path(saved).resolve()
    require((attempt / "result.json").is_file(),
            "Missing original source: exact original Native result")
    seal = read(attempt / "capture-seal.json")
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            seal.get("frames") == 600 and
            seal.get("events") == ["capture_finished", "encoders_closed",
                                   "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            all(seal.get("encoder_exit_codes", {}).get(name) == 0
                for name in CAMERAS),
            "Original Native capture/lifecycle incomplete")
    require(set(REQUIRED) <= set(seal.get("sources", {})),
            "Sealed original inventory incomplete")
    for name, expected in seal["sources"].items():
        path = (attempt / name).resolve()
        require(attempt in path.parents and path.is_file() and sha(path) == expected,
                "Sealed original source changed: " + name)
    exit_record = read(attempt / "native-exit.json")
    owner = read(Path(owner_path))
    require(exit_record.get("event") == "native_exit" and
            exit_record.get("capture_seal_sha256") == sha(attempt / "capture-seal.json") and
            owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json"),
            "Native exit or operator release missing")
    native = read(attempt / "result.json")
    require(native.get("case_id") == case_id and native.get("accepted") is False and
            native.get("video_frame_map_reference") == "video_frames.jsonl",
            "Original Native result identity or source map differs")
    processing = read(saved / "processing.json")
    require(processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("missing_evidence") is False and
            processing.get("native_revision", {}).get("construction_sha256") ==
            seal.get("native_revision", {}).get("construction_sha256"),
            "Saved-only processing does not bind original Native revision")
    require(processing.get("final_video_checks", {}).get("frames") == 600 and
            processing.get("final_video_checks", {}).get("passed") is True,
            "Full final video decode missing")
    saved_result_path = Path(processing.get("result", "")).resolve()
    require(saved in saved_result_path.parents and saved_result_path.is_file() and
            processing.get("result_sha256") == sha(saved_result_path) and
            read(saved_result_path).get("case_id") == case_id,
            "Saved analysis result is missing or unbound")
    for name in REQUIRED:
        require(processing.get("original_source_hashes", {}).get(name) ==
                sha(attempt / name), "Saved processing changed original: " + name)
    mapping, trace, evidence, native_rows = (
        rows(attempt / name) for name in
        ("video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl",
         "alley-native.jsonl"))
    require(all(len(table) == 600 for table in
                (mapping, trace, evidence, native_rows)),
            "Missing original 600-frame source join")
    for index, (m, t, e, n) in enumerate(zip(mapping, trace, evidence, native_rows)):
        frame, time = m.get("native_frame"), m.get("time_s")
        require(m.get("video_frame") == index and
                m.get("carla_frame") == frame and
                t.get("frame") == e.get("original_frame") == n.get("native_frame") == frame and
                abs(t.get("time_s", -1) - time) < 1e-4 and
                abs(e.get("recording_time_s", -1) - time) < 1e-4 and
                abs(n.get("t_s", -1) - time) < 1e-4 and
                n.get("diagnostic_fixture_only") is not True,
                "Original Native timestamp or actor source join differs")
    site, goods = read(attempt / "site-survey.json"), read(attempt / "goods-review.json")
    require(site.get("source_kind") == "original_native_alley_survey" and
            site.get("reviewer") and
            not site["reviewer"].startswith("diagnostic") and
            site.get("ordinance_status") in ("none_applicable", "applicable_otherwise") and
            goods.get("source_kind") == "independent_original_video_review" and
            goods.get("full_interval_reviewed") is True and
            not goods.get("diagnostic_fixture_only") and
            goods.get("reviewer"),
            "Original alley, district, ordinance or goods review missing")
    pixel = read(Path(pixel_review_path))
    require(pixel.get("case_id") == case_id and
            pixel.get("source_kind") == "independent_original_camera_pixel_review" and
            pixel.get("reviewer") and pixel.get("frame_count") == 600 and
            set(pixel.get("views", {})) == set(CAMERAS),
            "Actual original camera pixel review missing")
    for name in CAMERAS:
        require(pixel["views"][name].get("video_sha256") ==
                sha(attempt / (name + ".mkv")) and
                pixel["views"][name].get("vehicle_and_goods_visible") is True,
                "Actual original pixels or subject visibility missing: " + name)
    require(goods.get("video_sha256") == {name: sha(attempt / (name + ".mkv"))
                                            for name in CAMERAS},
            "Independent goods review is not bound to original pixels")
    stopped = sum(n.get("velocity_xyz_mps") == [0, 0, 0] and
                  n.get("alley_boundary_source_id") == site.get("alley_boundary_source_id")
                  for n in native_rows)
    require(stopped > 0, "Original alley stopping physically unverified")
    return {"format": "c378809-independent-delivery-source-audit-v1",
            "case_id": case_id, "checks": ["native_source", "all_participants",
                                        "time_join", "full_video_decode",
                                        "actual_pixels", "physical_completion"],
            "original_stopped_in_alley_frames": stopped,
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "saved_processing_sha256": sha(saved / "processing.json"),
            "pixel_review_sha256": sha(Path(pixel_review_path)),
            "expeditiousness": None, "legal_result": None,
            "limitations": ["Local legal determination remains independent of these measurements"]}


def self_test(case_id, negative):
    package = Path(__file__).resolve().parent
    receipt = package / "proofs" / (case_id.rsplit("__", 1)[-1] + "-compatibility.json")
    if negative:
        audit(case_id, package / "missing-original-attempt",
              package / "missing-saved", package / "missing-owner",
              package / "missing-review")
    proof = read(receipt)
    require(proof.get("case_id") == case_id and proof.get("passed") is True and
            {"actual_analysis", "four_camera_sources", "final_decode",
             "negative_case_source"} <= set(proof.get("checks", [])) and
            proof.get("scope") == "diagnostic software compatibility only",
            "Source-shaped CPU compatibility proof invalid")
    print(json.dumps({"case_id": case_id, "cpu_predicates_passed": True,
                      "original_native_acceptance_claimed": False}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--negative", action="store_true")
    parser.add_argument("--attempt")
    parser.add_argument("--saved")
    parser.add_argument("--owner-release")
    parser.add_argument("--pixel-review")
    args = parser.parse_args()
    if args.self_test:
        self_test(args.case, args.negative)
    else:
        require(all((args.attempt, args.saved, args.owner_release,
                     args.pixel_review)), "Original audit paths required")
        print(json.dumps(audit(args.case, args.attempt, args.saved,
                               args.owner_release, args.pixel_review), indent=2))

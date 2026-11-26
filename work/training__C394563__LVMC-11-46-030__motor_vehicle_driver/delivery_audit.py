"""Independent saved school-warning source audit; never issues a legal verdict."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("road.xodr", "native-rows.jsonl", "video_frames.jsonl", "trace.jsonl",
           "original-school-lane-review.json", "captured-source-hashes.json") + tuple(
               name + ".mkv" for name in CAMERAS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(case, candidate, attempt, processing, diagnostic=False, omit_source=None,
          variant=False):
    manifest_path = ROOT / ("draft-variant-manifest.json" if variant else "execution-manifest.json")
    if not manifest_path.is_file() and not variant:
        manifest_path = ROOT / "draft-native-manifest.json"
    manifest = read(manifest_path)
    entry = next((item for item in manifest["cases"] if item["case_id"] == case), None)
    if entry is None:
        raise ValueError("Unknown exact school-warning case")
    selected = entry if candidate == "primary" else next(
        (item for item in entry["candidates"] if item["id"] == candidate), None)
    if selected is None:
        raise ValueError("Unknown exact school-warning candidate")
    saved = read(processing)
    if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
            saved.get("originals_preserved") is not True or saved.get("case_id") != case or
            saved.get("candidate_id") != candidate or
            saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"] or
            saved.get("timestamp_joins", {}).get("frames") != 600 or
            saved.get("final_video_checks", {}).get("frames") != 600):
        raise ValueError("Saved processing, source identity or full decode differs")
    stage = Path(saved["analysis_directory"]).resolve()
    original = Path(attempt).resolve()
    hashes = {}
    for name in SOURCES:
        if name == omit_source:
            raise ValueError("Missing source: " + name)
        path = stage / name
        if not path.is_file():
            raise ValueError("Missing source: " + name)
        hashes[name] = sha(path)
        if not (original / name).is_file() or sha(original / name) != hashes[name]:
            raise ValueError("Original source differs from saved stage: " + name)
    seal = read(stage / "captured-source-hashes.json")
    if seal.get("case_id") != case or seal.get("source_kind") != "original_native_capture":
        raise ValueError("Original school-warning inventory identity differs")
    if any(seal.get("sha256", {}).get(name) != hashes[name] for name in SOURCES if name in seal.get("sha256", {})):
        raise ValueError("Original school-warning inventory hash differs")
    native, mapping, trace = rows(stage / "native-rows.jsonl"), rows(stage / "video_frames.jsonl"), rows(stage / "trace.jsonl")
    if len(native) != len(mapping) or len(mapping) != len(trace) or len(native) != 600:
        raise ValueError("School-warning source frame coverage incomplete")
    for index, (record, frame, motion) in enumerate(zip(native, mapping, trace)):
        if (record.get("video_frame") != index or frame.get("video_frame") != index or
                record.get("native_frame") != frame.get("native_frame") or
                motion.get("frame") != frame.get("carla_frame") or
                abs(motion.get("time_s", -1) - frame.get("time_s", -10)) > 1e-4 or
                any(record.get("camera_native_frames", {}).get(name) != frame["native_frame"]
                    for name in CAMERAS) or
                any(record.get(key) is None for key in
                    ("vehicle_actor_id", "warning_actor_id", "child_actor_id"))):
            raise ValueError("School-warning participant, time or four-view join differs")
    result = read(stage / "result.json")
    report = read(stage / "analysis-report.json")
    measured = report.get("measurements", {}).get("school_warning_stop", {})
    if (result.get("case_id") != case or measured.get("method") != "derive" or
            any(measured.get("sources", {}).get(name) != hashes[name] for name in
                ("road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                 "original-school-lane-review.json")) or
            measured.get("value", {}).get("frame_count") != 600):
        raise ValueError("Independent measured source binding differs")
    review = read(stage / "original-school-lane-review.json")
    if review.get("school_pedestrian_lane_survey") is not True:
        raise ValueError("Original school pedestrian lane unreviewed")
    for field in ("school_lane_source", "child_identity_source", "warning_asset_source",
                  "municipal_jurisdiction_source"):
        name = "review-" + field
        path = stage / name
        if not path.is_file() or sha(path) != review.get(field + "_sha256"):
            raise ValueError("Original independent review source missing: " + field)
    if diagnostic:
        suffix = case.rsplit("__", 1)[1]
        prefix = "variant-" if variant else ""
        compatibility = read(ROOT / "proofs" / f"{prefix}{suffix}-{candidate}-compatibility.json")
        if (compatibility.get("passed") is not True or
                compatibility.get("construction_sha256") != selected["construction_sha256"]):
            raise ValueError("Diagnostic compatibility source missing")
    else:
        provenance = read(original / "acquisition-provenance.json")
        if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is True:
            raise ValueError("Independent original Native acquisition required")
        pixel = read(stage / "pixel-review.json")
        if (pixel.get("review_status") != "independently_reviewed" or not pixel.get("reviewer") or
                any(pixel.get("camera_sha256", {}).get(name) != hashes[name + ".mkv"]
                    for name in CAMERAS) or
                pixel.get("lane_child_warning_visible") is not True):
            raise ValueError("Original four-view school warning pixels unreviewed")
        physical = result.get("physical_checks", {}).get("maneuver", {})
        if physical.get("status") != "met" or result.get("maneuver_completed") is not True:
            raise ValueError("Original physical progression unverified")
    return {"format": "worker-school-warning-independent-delivery-audit-v1",
            "case_id": case, "candidate_id": candidate,
            "construction_sha256": selected["construction_sha256"],
            "saved_processing_sha256": sha(processing),
            "original_source_sha256": hashes,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "diagnostic_only": diagnostic, "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--candidate", default="primary")
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processing", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--variant", action="store_true")
    parser.add_argument("--omit-source", choices=SOURCES)
    args = parser.parse_args()
    if args.omit_source and not args.diagnostic:
        raise ValueError("Source omission is diagnostic only")
    result = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic, args.omit_source, args.variant)
    if args.output.exists():
        raise ValueError("Retain prior independent delivery audit")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "case_id": args.case,
                      "diagnostic_only": args.diagnostic}))

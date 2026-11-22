"""Independent selected-case diagnostic delivery check; never original acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
           "road_geometry.json", "road.xodr", *(name + ".mkv" for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(case_id, negative=False):
    manifest = read(HERE / "execution-manifest.json")
    entry = next((row for row in manifest["cases"] if row["case_id"] == case_id), None)
    require(entry is not None and entry["kind"] == "delivery", "Unselected delivery case")
    expected = "0" * 64 if negative else entry["construction_sha256"]
    require(sha(HERE / entry["construction"]) == expected,
            "Delivery construction differs from selected manifest")
    suffix = case_id.removeprefix(HERE.name + "__")
    proof_dir = HERE / "current-runtime-selected-proof" / suffix / "primary"
    compatibility = read(proof_dir / "compatibility.json")
    saved_path = proof_dir / "saved-processing.json"
    saved = read(saved_path)
    audit_path = proof_dir / "source-camera-audit.json"
    source_audit = read(audit_path)
    physical_path = HERE / entry["physical_preparation"]["receipt"]
    physical = read(physical_path)
    require(sha(physical_path) == entry["physical_preparation"]["sha256"] and
            compatibility["passed"] is True and
            compatibility["runtime_manifest_sha256"] == manifest["runtime_manifest_sha256"] and
            compatibility["construction_sha256"] == entry["construction_sha256"] and
            saved["passed"] is True and saved["recorded_only"] is True and
            saved["originals_preserved"] is True and saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False and
            source_audit["camera_source_shape_passed"] is True and
            source_audit["original_native_acceptance_rejected"] is True and
            source_audit["saved_processing_sha256"] == sha(saved_path) and
            source_audit["construction_sha256"] == entry["construction_sha256"] and
            physical["fixtures_are_cpu_mocks"] is True and
            physical["original_native_motion_verified"] is False,
            "Current diagnostic chain or physical boundary differs")
    attempts = [path for path in (ROOT / ".runtime-work").glob("c111256-current-*-compat")
                if (path / "compatibility.json").is_file() and
                sha(path / "compatibility.json") == sha(proof_dir / "compatibility.json")]
    require(len(attempts) == 1, "Current retained source attempt missing or ambiguous")
    attempt = attempts[0]
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    require(source_hashes == source_audit["source_sha256"] and
            all(saved["original_source_hashes"].get(name) == value
                for name, value in source_hashes.items()),
            "Retained diagnostic source differs")
    rows = [json.loads(line) for line in (attempt / "native_samples.jsonl").read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / "video_frames.jsonl").read_text().splitlines()]
    events = [json.loads(line) for line in (attempt / "capture/evidence.jsonl").read_text().splitlines()]
    require(len(rows) == len(frames) == len(events) == 480 and all(
        frame["video_frame"] == i and row["native_frame"] == frame["native_frame"] ==
        event["original_frame"] and row.get("speed_provenance") == "synthetic_native_sample" and
        event.get("synthetic_diagnostic") is True
        for i, (row, frame, event) in enumerate(zip(rows, frames, events))),
        "Diagnostic frame, time or speed provenance differs")
    result_path = Path(saved["result"])
    result = read(result_path)
    require(sha(result_path) == saved["result_sha256"] and
            result["accepted"] is False and result["maneuver_completed"] is False and
            result["legal_verdict_claimed"] is False,
            "Diagnostic result claims original acceptance")
    return {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "source_sha256": source_hashes, "four_camera_sources": list(CAMERAS),
            "joined_frames": 480, "source_audit_sha256": sha(audit_path),
            "physical_fixture_branches_tested": len(physical["fixtures"]),
            "lifecycle_fixture_tested": physical["lifecycle"]["exit_code"] == 0,
            "actual_pixels_reviewed": False, "delivery_accepted": False,
            "original_native_motion_verified": False, "auditor_sha256": sha(Path(__file__))}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.negative)))

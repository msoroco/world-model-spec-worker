"""Read-only selected alley diagnostic chain audit; never original acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(case_id, *, negative=False):
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    entry = next((x for x in manifest["cases"] if x["case_id"] == case_id), None)
    require(entry is not None, "Unselected alley case")
    expected = "0" * 64 if negative else entry["construction_sha256"]
    require(sha(HERE / entry["construction"]) == expected,
            "Delivery construction differs from selected manifest")
    suffix = case_id.removeprefix(HERE.name + "__")
    attempt = ROOT / ".runtime-work" / f"c10014-update034-{suffix}-primary-compat"
    saved_path = ROOT / ".runtime-work" / f"c10014-update034-{suffix}-primary-saved/v0001/processing.json"
    saved = json.loads(saved_path.read_text())
    compat = json.loads((HERE / entry["compatibility"]["receipt"]).read_text())
    physical = json.loads((HERE / entry["physical_preparation"]["receipt"]).read_text())
    require(compat["passed"] is True and compat["case_id"] == case_id and
            compat["construction_sha256"] == entry["construction_sha256"],
            "Selected compatibility differs")
    require(saved["passed"] is True and saved["recorded_only"] is True and
            saved["case_id"] == case_id and saved["candidate_id"] == "primary" and
            saved["native_revision"]["construction_sha256"] == entry["construction_sha256"] and
            saved["originals_preserved"] is True and saved["missing_evidence"] is False and
            saved["physical_acceptance_claimed"] is False and saved["legal_acceptance_claimed"] is False and
            saved["timestamp_joins"]["passed"] is True,
            "Selected saved diagnostic processing differs")
    require(physical["fixtures_are_cpu_mocks"] is True and
            physical["original_native_motion_verified"] is False and
            physical["alley_access_or_legal_blockage_verified"] is False,
            "Alley physical mock promoted")
    required = ("native_samples.jsonl", "road_geometry.json", "video_frames.jsonl",
                "capture/evidence.jsonl", "body_history.jsonl", "trace.jsonl",
                *(camera + ".mkv" for camera in CAMERAS))
    hashes = {}
    for name in required:
        source = attempt / name
        require(source.is_file(), "Missing diagnostic source: " + name)
        digest = sha(source)
        require(saved["original_source_hashes"].get(name) == digest,
                "Saved diagnostic source changed: " + name)
        hashes[name] = digest
    native = [json.loads(x) for x in (attempt / "native_samples.jsonl").read_text().splitlines()]
    frame_map = [json.loads(x) for x in (attempt / "video_frames.jsonl").read_text().splitlines()]
    require(len(native) == len(frame_map) == 480 and all(
        frame["video_frame"] == i and frame["native_frame"] == sample["native_frame"] and
        abs(frame["time_s"] - sample["time_s"]) <= 1e-4
        for i, (frame, sample) in enumerate(zip(frame_map, native))),
        "Diagnostic frame join differs")
    require(all(row.get("synthetic_diagnostic") is True and
                row.get("speed_provenance") == "synthetic_native_sample" for row in native),
            "Diagnostic speed provenance differs")
    result = json.loads((attempt / "result.json").read_text())
    require(saved["result_sha256"] == sha(attempt / "result.json") and
            result["provenance_kind"] == "synthetic_local_diagnostic" and
            result["maneuver_completed"] is False and result["accepted"] is False and
            result["legal_verdict_claimed"] is False,
            "Diagnostic physical or legal acceptance claimed")
    return {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "source_shape_passed": True, "source_sha256": hashes, "joined_frames": 480,
            "four_camera_sources": list(CAMERAS), "actual_pixels_reviewed": False,
            "alley_access_or_legal_blockage_verified": False,
            "delivery_accepted": False, "original_native_motion_verified": False,
            "auditor_sha256": sha(Path(__file__))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, negative=args.negative)))


if __name__ == "__main__":
    main()

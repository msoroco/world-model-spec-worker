"""Independent CPU audit of selected diagnostic source chains, never acceptance."""
import argparse
import hashlib
import json
import shlex
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
    require(entry is not None, "Unselected delivery case")
    expected_construction_sha = "0" * 64 if negative else entry["construction_sha256"]
    require(sha(HERE / entry["construction"]) == expected_construction_sha,
            "Delivery construction differs from selected manifest")
    tokens = shlex.split(entry["offline"]["command"])
    run = ROOT / tokens[tokens.index("--output") + 1]
    attempt = run.parent / "compatibility"
    saved = json.loads((run.parent / "saved/v0001/processing.json").read_text())
    compat = json.loads((HERE / entry["compatibility"]["receipt"]).read_text())
    proof = json.loads((HERE / entry["physical_preparation"]["receipt"]).read_text())
    require(compat["passed"] is True and compat["case_id"] == case_id and
            compat["construction_sha256"] == entry["construction_sha256"],
            "Compatibility binding differs")
    require(saved["passed"] is True and saved["case_id"] == case_id and
            saved["candidate_id"] == "primary" and saved["originals_preserved"] is True and
            saved["physical_acceptance_claimed"] is False and saved["legal_acceptance_claimed"] is False and
            saved["timestamp_joins"]["passed"] is True,
            "Saved diagnostic processing differs")
    require(proof["case_id"] == case_id and proof["construction_sha256"] == entry["construction_sha256"] and
            proof["fixtures_are_cpu_mocks"] is True and proof["original_native_motion_verified"] is False,
            "Mock physical branch promoted")
    required = ("native_samples.jsonl", "road_geometry.json", "video_frames.jsonl",
                "capture/evidence.jsonl", "body_history.jsonl", "trace.jsonl",
                *(name + ".mkv" for name in CAMERAS))
    hashes = {}
    for name in required:
        source = attempt / name
        require(source.is_file(), "Missing delivery source: " + name)
        digest = sha(source)
        require(saved["original_source_hashes"].get(name) == digest,
                "Saved original diagnostic source changed: " + name)
        hashes[name] = digest
    rows = [json.loads(x) for x in (attempt / "native_samples.jsonl").read_text().splitlines()]
    mapping = [json.loads(x) for x in (attempt / "video_frames.jsonl").read_text().splitlines()]
    require(len(rows) == len(mapping) == 480 and all(
        frame["video_frame"] == i and frame["native_frame"] == sample["native_frame"] and
        abs(frame["time_s"] - sample["time_s"]) <= 1e-4
        for i, (frame, sample) in enumerate(zip(mapping, rows))),
        "Diagnostic frame/time join differs")
    require(all(row.get("synthetic_diagnostic") is True and
                row.get("speed_provenance") == "synthetic_native_sample" for row in rows),
            "Diagnostic speed provenance differs")
    result = json.loads((attempt / "result.json").read_text())
    require(saved["result_sha256"] == sha(attempt / "result.json") and
            result["accepted"] is False and result["maneuver_completed"] is False and
            result["legal_verdict_claimed"] is False,
            "Diagnostic result promoted to physical acceptance")
    return {"case_id": case_id, "construction_sha256": entry["construction_sha256"],
            "source_shape_passed": True, "source_sha256": hashes,
            "four_camera_sources": list(CAMERAS), "joined_frames": 480,
            "physical_fixture_branches_tested": 3, "lifecycle_fixture_tested": True,
            "actual_pixels_reviewed": False, "delivery_accepted": False,
            "original_native_motion_verified": False, "auditor_sha256": sha(Path(__file__))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.case, negative=args.negative)))


if __name__ == "__main__":
    main()

"""Read-only original-source boundary for local C10014 delivery review.

This script cannot accept a CPU fixture. The local adopter supplies a sealed
Native attempt, operator release receipt, saved processing, full decode receipt,
and source-bound review of actual source-camera pixels before acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ORIGINALS = ("trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
             "native_samples.jsonl", "body_history.jsonl", "capture/manifest.json",
             "road_geometry.json")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    require(path.is_file(), "Missing original source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def check_original_rows(attempt: Path, expected_frames: int) -> dict:
    """Independently join Native body, trace, evidence, and camera map rows."""
    sources = {name: rows(attempt / name) for name in ORIGINALS[:5]}
    require(all(len(source) == expected_frames for source in sources.values()),
            "Missing original Native body/frame rows")
    trace, evidence, mapping, motion, body = (sources[name] for name in ORIGINALS[:5])
    previous_frame, previous_time = -1, -math.inf
    for index, (t, e, m, n, b) in enumerate(zip(trace, evidence, mapping, motion, body)):
        frame, time_s = m.get("native_frame"), m.get("time_s")
        require(type(frame) is int and frame > previous_frame and
                type(time_s) in (int, float) and math.isfinite(time_s) and
                time_s > previous_time and m.get("video_frame") == index and
                m.get("carla_frame") == frame and
                t.get("frame") == e.get("original_frame") ==
                n.get("native_frame") == b.get("frame") == frame,
                "Original Native frame join differs")
        require(all(type(row.get(key)) in (int, float) and
                    abs(row[key] - time_s) <= 1e-4
                    for row, key in ((t, "time_s"), (e, "recording_time_s"),
                                     (n, "time_s"), (b, "time_s"))),
                "Original Native timestamp join differs")
        require(not any(row.get("synthetic_diagnostic") is True
                        for row in (t, e, n, b)) and
                n.get("speed_provenance") != "synthetic_native_sample" and
                t.get("speed_provenance") != "synthetic_native_sample" and
                e.get("ego", {}).get("speed_provenance") != "synthetic_native_sample",
                "Synthetic diagnostic cannot establish original Native motion")
        vertices = n.get("native_body_xy_m")
        require(isinstance(vertices, list) and len(vertices) == 4 and
                all(isinstance(v, list) and len(v) == 2 and
                    all(type(x) in (int, float) and math.isfinite(x) for x in v)
                    for v in vertices) and
                type(n.get("speed_mps")) in (int, float) and
                math.isfinite(n["speed_mps"]) and n["speed_mps"] >= 0,
                "Original Native body or velocity missing")
        previous_frame, previous_time = frame, time_s
    return {"frames": expected_frames, "first_frame": mapping[0]["native_frame"],
            "last_frame": mapping[-1]["native_frame"],
            "frame_map_sha256": sha(attempt / "video_frames.jsonl")}


def check_native_boundary(attempt: Path, saved: Path, owner_receipt: Path,
                          case_id: str, construction_sha256: str) -> dict:
    """Reject absent closure, changed original bytes, and derived false success."""
    attempt, saved = attempt.resolve(), saved.resolve()
    require((attempt / "capture-seal.json").is_file(), "Missing sealed Native capture")
    seal = read(attempt / "capture-seal.json")
    require(seal.get("format") == "worker-sealed-capture" and
            seal.get("provenance_kind") == "native" and
            seal.get("diagnostic_fixture") is False and
            seal.get("physical_acceptance_claimed") is False and
            seal.get("frames") == 480 and
            seal.get("events") == ["capture_finished", "encoders_closed", "restoration_verified"] and
            seal.get("restoration", {}).get("restored") is True and
            set(seal.get("encoder_exit_codes", {})) == set(CAMERAS) and
            all(code == 0 for code in seal["encoder_exit_codes"].values()) and
            seal.get("native_revision", {}).get("construction_sha256") == construction_sha256 and
            seal["native_revision"].get("runner_sha256") == sha(attempt / "runner.py"),
            "Native capture seal or lifecycle incomplete")
    require(set(ORIGINALS + tuple(name + ".mkv" for name in CAMERAS)) <=
            set(seal.get("sources", {})), "Sealed original source inventory incomplete")
    for name, checksum in seal["sources"].items():
        source = (attempt / name).resolve()
        require(attempt in source.parents and source.is_file() and sha(source) == checksum,
                "Sealed original source changed: " + name)
    capture = read(attempt / "capture/manifest.json")
    require(capture.get("extraction_confirmed") is True and
            capture.get("frames") == 480 and
            capture.get("synthetic_diagnostic") is not True,
            "Native extraction missing or synthetic")
    exit_record = read(attempt / "native-exit.json")
    require(exit_record.get("event") == "native_exit" and
            exit_record.get("capture_seal_sha256") == sha(attempt / "capture-seal.json") and
            exit_record.get("native_revision") == seal["native_revision"],
            "Native exit differs from sealed capture")
    owner = read(owner_receipt)
    require(owner.get("event") == "owner_released" and
            owner.get("operator_attested") is True and
            owner.get("native_exit_sha256") == sha(attempt / "native-exit.json") and
            owner.get("native_construction_sha256") == construction_sha256,
            "Operator owner release absent or stale")
    original = check_original_rows(attempt, 480)
    processing = read(saved / "processing.json")
    require(processing.get("case_id") == case_id and
            processing.get("passed") is True and
            processing.get("recorded_only") is True and
            processing.get("missing_evidence") is False and
            processing.get("native_revision", {}).get("construction_sha256") == construction_sha256,
            "Saved processing lacks original Native evidence")
    for name in ORIGINALS + tuple(camera + ".mkv" for camera in CAMERAS):
        require(processing.get("original_source_hashes", {}).get(name) == sha(attempt / name),
                "Saved processing changed original source: " + name)
    result_path = Path(processing["result"]).resolve()
    require(saved in result_path.parents and result_path.is_file(),
            "Saved result escapes selected processing version")
    result = read(result_path)
    checks = result.get("physical_checks", {})
    require(result.get("case_id") == case_id and
            result.get("provenance_kind") == "native" and
            result.get("accepted") is False and
            result.get("legal_verdict_claimed") is False and
            result.get("maneuver_completed") is True and
            all(checks.get(name, {}).get("status") == "met" and
                checks[name].get("sources") for name in ("setup", "target", "maneuver", "attempt")),
            "Physical completion lacks original measured support")
    return {**original, "case_id": case_id, "result_sha256": sha(result_path),
            "capture_seal_sha256": sha(attempt / "capture-seal.json"),
            "owner_release_sha256": sha(owner_receipt),
            "physical_completion": "measured; legal blocking judgment remains separate"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--saved", type=Path, required=True)
    parser.add_argument("--owner-receipt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--construction-sha256", required=True)
    args = parser.parse_args()
    print(json.dumps(check_native_boundary(args.attempt, args.saved,
          args.owner_receipt, args.case, args.construction_sha256), indent=2))


if __name__ == "__main__":
    main()

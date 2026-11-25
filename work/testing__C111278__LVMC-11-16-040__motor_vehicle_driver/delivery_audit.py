"""Independent recorded-only audit before any case is considered delivered.

This verifies joins and provenance, not law, physical visibility, or video quality.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
from pathlib import Path
import json
import subprocess

from saved_sight import verify as verify_saved


class DeliveryError(ValueError):
    pass


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
ASSIGNMENT = "testing__C111278__LVMC-11-16-040__motor_vehicle_driver"
CASES = {"blocked_below", "blocked_at", "blocked_above", "clear_at",
         "through_blocked", "controlled_blocked"}


def _decode_video(path: Path, expected_frames: int) -> dict:
    command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-i",
               str(path), "-an", "-f", "framemd5", "-"]
    process = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if process.returncode:
        raise DeliveryError("full video decode failed: " + path.name)
    rows = [line for line in process.stdout.splitlines() if line and not line.startswith("#")]
    if len(rows) != expected_frames:
        raise DeliveryError("full video frame count differs: " + path.name)
    return {"decoded_frames": len(rows), "decoded_pixel_records_sha256": sha256(process.stdout.encode()).hexdigest()}


def audit(receipt: dict, measurement: dict, source_root: Path, expected_case: str,
          full_video_decode: bool = False) -> dict:
    if receipt.get("case_id") != expected_case or measurement.get("case_id") != expected_case:
        raise DeliveryError("case binding differs")
    if receipt.get("map_hash") != measurement.get("map_hash"):
        raise DeliveryError("map identity differs")
    diagnostic = receipt.get("diagnostic_fixture") is True
    if diagnostic:
        source = source_root / "fixture-provenance.json"
        if (receipt.get("capture_kind") != "synthetic_fixture" or not source.is_file() or
                json.loads(source.read_text()).get("physical_acceptance_claimed") is not False):
            raise DeliveryError("untrusted synthetic audit source")
    elif receipt.get("recorded_only") is not True or receipt.get("capture_kind") != "original_native":
        raise DeliveryError("original saved acquisition required")
    if receipt.get("fps") != 20 or receipt.get("duration_s") != 45:
        raise DeliveryError("20 Hz, 45-second acquisition contract differs")
    streams = receipt.get("streams")
    if not isinstance(streams, dict) or set(streams) != set(CAMERAS):
        raise DeliveryError("four-camera source inventory incomplete")
    decoded = {}
    for name, item in streams.items():
        relative = item.get("path", "")
        if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise DeliveryError(f"unsafe or missing {name} path")
        file = source_root / relative
        if not file.is_file() or sha256(file.read_bytes()).hexdigest() != item.get("sha256"):
            raise DeliveryError(f"{name} bytes missing or changed")
        if full_video_decode:
            decoded[name] = _decode_video(file, 900)
    frame_ids = receipt.get("frame_ids")
    if not isinstance(frame_ids, list) or len(frame_ids) != 900:
        raise DeliveryError("full original frame map missing")
    if any(b != a + 1 for a, b in zip(frame_ids, frame_ids[1:])):
        raise DeliveryError("frame map not contiguous")
    if not set(measurement.get("approach_frame_ids", [])).issubset(frame_ids):
        raise DeliveryError("approach frames not in original acquisition")
    if not set(measurement.get("traversal_frame_ids", [])).issubset(frame_ids):
        raise DeliveryError("traversal frames not in original acquisition")
    if not measurement.get("source_sha256"):
        raise DeliveryError("measurement provenance absent")
    if full_video_decode:
        census_path = source_root / "actor-census.jsonl"
        if (not census_path.is_file() or
                sha256(census_path.read_bytes()).hexdigest() != receipt.get("actor_census_sha256")):
            raise DeliveryError("actor census missing or changed")
        census = [json.loads(line) for line in census_path.read_text().splitlines()]
        arms = receipt.get("entering_arms")
        if (not isinstance(arms, list) or len(arms) < 3 or
                len(census) != 900 or
                any(row.get("frame") != frame or row.get("entering_arms") != arms or
                    not isinstance(row.get("actors"), list)
                    for row, frame in zip(census, frame_ids))):
            raise DeliveryError("all-frame entering-arm actor inventory incomplete")
    if receipt.get("candidate") not in ("primary", "fallback1", "fallback2"):
        raise DeliveryError("candidate-selection receipt absent")
    return {"case_id": expected_case, "recorded_only_join": "passed",
            "full_video_decode": decoded, "diagnostic_fixture": diagnostic,
            "legal_conclusion": None}


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _output_path(path: Path) -> Path:
    path = path.resolve()
    if ".runtime-work" not in path.parts or path.exists():
        raise DeliveryError("new audit output must be under .runtime-work")
    return path


def run_production(case_id: str, attempt: Path, processed: Path) -> dict:
    """Audit a real saved attempt using its sealed Native and processing sources."""
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in CASES}:
        raise DeliveryError("unknown exact case")
    attempt, processed = attempt.resolve(), processed.resolve()
    if not attempt.is_dir() or not processed.is_dir():
        raise DeliveryError("attempt and processed directories required")
    if (attempt / "fixture-provenance.json").exists():
        raise DeliveryError("diagnostic fixture cannot be a production audit")
    processing_path = processed / "processing.json"
    if not processing_path.is_file():
        raise DeliveryError("saved processing receipt missing")
    processing = json.loads(processing_path.read_text())
    if (processing.get("case_id") != case_id or processing.get("passed") is not True or
            processing.get("recorded_only") is not True or
            processing.get("originals_preserved") is not True or
            processing.get("missing_evidence") is not False):
        raise DeliveryError("saved processing did not preserve exact original sources")
    saved = verify_saved(attempt, case_id)
    measured = saved["measurement"]
    if saved["camera_capture"] == "unverified":
        raise DeliveryError("four original Native cameras required")
    native_path = attempt / "native-sight-receipt.json"
    native = json.loads(native_path.read_text())
    packet_path = attempt / "native-sight.json"
    packet = json.loads(packet_path.read_text())
    frames = packet["frames"]
    mapping_path = attempt / "video_frames.jsonl"
    mapping = [json.loads(line) for line in mapping_path.read_text().splitlines()]
    if (len(mapping) != 900 or any(
            row.get("carla_frame") != frame["frame"] or row.get("time_s") != frame["time_s"]
            for row, frame in zip(mapping, frames))):
        raise DeliveryError("video frame map differs from original Native source")
    report_path = attempt / "analysis-report.json"
    report = json.loads(report_path.read_text())
    if (report.get("case_id") != case_id or report.get("analysis_complete") is not True or
            report.get("diagnostic_fixture") is not False):
        raise DeliveryError("source-bound original analysis report required")
    result_path = attempt / "result.json"
    result = json.loads(result_path.read_text())
    if result.get("case_id") != case_id or result.get("diagnostic_fixture") is True:
        raise DeliveryError("saved result case or provenance differs")
    if processing.get("result_sha256") != _sha(result_path):
        raise DeliveryError("saved processing result hash differs")
    streams = {name: {"path": name + ".mkv", "sha256": _sha(attempt / (name + ".mkv"))}
               for name in CAMERAS}
    census_path = attempt / "actor-census.jsonl"
    originals = processing.get("original_source_hashes")
    critical = ["native-sight.json", "native-sight-receipt.json", "video_frames.jsonl",
                "actor-census.jsonl", "analysis-report.json", "result.json",
                *(name + ".mkv" for name in CAMERAS)]
    if not isinstance(originals, dict) or any(
            originals.get(name) != _sha(attempt / name) for name in critical):
        raise DeliveryError("saved processing original-source hashes differ")
    receipt = {"case_id": case_id, "map_hash": native["map_hash"],
               "recorded_only": native["recorded_only"],
               "capture_kind": native["capture_kind"], "fps": native["fps"],
               "duration_s": native["duration_s"], "streams": streams,
               "frame_ids": [frame["frame"] for frame in frames],
               "candidate": processing.get("candidate_id"),
               "entering_arms": packet["entering_arms"],
               "actor_census_sha256": _sha(census_path)}
    checked = audit(receipt, measured, attempt, case_id, full_video_decode=True)
    return {"format": "c111278-production-delivery-audit-v1", "case_id": case_id,
            "source_join_passed": True, "original_native": True,
            "source_processing_sha256": _sha(processing_path),
            "source_sight_sha256": _sha(packet_path),
            "source_result_sha256": _sha(result_path),
            "source_analysis_sha256": _sha(report_path),
            "source_video_frame_map_sha256": _sha(mapping_path),
            "source_actor_census_sha256": _sha(census_path),
            "audit": checked, "physical_visibility_claimed": False,
            "legal_conclusion": None}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Audit one original C111278 saved attempt")
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--processed", type=Path, required=True,
                        help="version directory containing processing.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = _output_path(args.output)
    value = run_production(args.case, args.attempt, args.processed)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

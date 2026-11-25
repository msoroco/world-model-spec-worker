"""Independently review a sealed bicycle attempt's saved source protocol.

Diagnostic mode tests source joins and all original PNG payloads. It never
produces a canonical physical acceptance receipt. Production review requires
reviewed source authority and a separate canonical video/Core pixel audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from saved_attempt import process_saved
from saved_media_audit import audit_saved_media


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: Path, authority: Path, site_file: Path, case_id: str,
          diagnostic_protocol: bool = False) -> dict:
    attempt = attempt.resolve()
    authority = authority.resolve()
    site_file = site_file.resolve()
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("exact delivery case identity differs")
    site = json.loads(site_file.read_text(encoding="utf-8"))
    if not diagnostic_protocol and site.get("reviewed_original_site") is not True:
        raise ValueError("reviewed original site authority missing")
    saved = process_saved(attempt, authority, site, case_id,
                          allow_diagnostic=diagnostic_protocol)
    original = audit_saved_media(attempt, case_id)
    if saved["original_media_audit"] != original:
        raise ValueError("independent original camera audit differs")
    measurement = saved["measurement"]
    if measurement.get("duration_frames") != original["frame_count"]:
        raise ValueError("original measurement and camera frame count differ")
    if original["decoded_original_images"] != 4 * original["frame_count"]:
        raise ValueError("four full original camera sequences required")
    if measurement.get("straight_route_observed") is not True:
        raise ValueError("straight bicycle route not observed")
    if not isinstance(measurement.get("entry_frame"), int):
        raise ValueError("bicycle entry frame missing")
    receipt = json.loads((attempt / "attempt.json").read_text(encoding="utf-8"))
    if receipt.get("diagnostic_fixture") is True and not diagnostic_protocol:
        raise ValueError("diagnostic capture cannot establish original delivery")
    return {
        "format": "c111125-delivery-source-protocol-v1",
        "assignment_id": ASSIGNMENT,
        "case_id": case_id,
        "attempt_receipt_sha256": _sha(attempt / "attempt.json"),
        "site_source_sha256": _sha(site_file),
        "frame_count": original["frame_count"],
        "decoded_original_images": original["decoded_original_images"],
        "checks": {"native_source": True, "all_participants": True,
                   "time_join": True, "full_original_png_decode": True,
                   "original_png_hashes": True},
        "diagnostic_fixture": saved["diagnostic_fixture"],
        "source_protocol_passed": True,
        "canonical_video_core_audit_pending": True,
        "physical_acceptance": False,
        "legal_verdict": None,
    }


def audit_processed(attempt: Path, processed: Path, case_id: str,
                    diagnostic_protocol: bool = False, *,
                    authority: Path | None = None, site_file: Path | None = None) -> dict:
    """Independently verify pinned saved processing and all original camera pixels.

    A diagnostic pass proves only the audit implementation. Production requires
    original Native provenance, measured physical completion, and no diagnostic
    marker in either the original acquisition or the saved result.
    """
    attempt = attempt.resolve()
    processed = processed.resolve()
    if case_id not in {ASSIGNMENT + "__" + name for name in
                       ("two_cycles_failed_detection", "one_cycle", "three_cycles",
                        "signal_changes", "no_prior_stop", "fails_to_yield")}:
        raise ValueError("exact delivery case identity differs")
    receipt_path = processed / "processing.json"
    result_path = processed / "analysis/result.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    joins = receipt.get("timestamp_joins", {})
    media = receipt.get("final_video_checks", {})
    if (receipt.get("format") != "worker-saved-processing" or
            receipt.get("case_id") != case_id or receipt.get("passed") is not True or
            receipt.get("recorded_only") is not True or
            receipt.get("originals_preserved") is not True or
            receipt.get("missing_evidence") is not False or
            receipt.get("result_sha256") != _sha(result_path) or
            result.get("case_id") != case_id or
            joins.get("passed") is not True or media.get("passed") is not True):
        raise ValueError("saved processing receipt changed or incomplete")
    count = joins.get("frames")
    if not isinstance(count, int) or count != 900 or media.get("frames") != count:
        raise ValueError("full original 900-frame join required")
    originals = receipt.get("original_source_hashes")
    if not isinstance(originals, dict) or not originals:
        raise ValueError("original source hashes missing")
    for name, digest in originals.items():
        source = (attempt / name).resolve()
        if not source.is_relative_to(attempt) or not source.is_file() or _sha(source) != digest:
            raise ValueError("original acquisition missing or changed: " + name)
    if not {name + ".mkv" for name in CAMERAS} <= set(originals):
        raise ValueError("four original camera sources missing")
    mapping = attempt / "video_frames.jsonl"
    if mapping.is_file() and "video_frames.jsonl" in originals:
        rows = [json.loads(line) for line in mapping.read_text(encoding="utf-8").splitlines()]
        if len(rows) != count or any(row.get("video_frame") != index for index, row in enumerate(rows)):
            raise ValueError("original frame map is incomplete")
        mapping_sha = _sha(mapping)
    else:
        raise ValueError("original frame map missing")
    trace = attempt / "trace.jsonl"
    if not trace.is_file() or "trace.jsonl" not in originals:
        raise ValueError("original trace missing")
    motion = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    if len(motion) != count or any(
            row.get("carla_frame") != sample.get("frame") or
            abs(row.get("time_s", -1) - sample.get("time_s", -2)) > 1e-6
            for row, sample in zip(rows, motion)):
        raise ValueError("original trace and video frame/time join differs")
    repo = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo / "runtime/scenario_pipeline"))
    from worker_exchange.media import audit as decode
    decoded = {name: decode(attempt / (name + ".mkv"), count,
                            mapping_sha256=mapping_sha)
               for name in CAMERAS}
    if not all(value.get("passed") is True for value in decoded.values()):
        raise ValueError("original camera pixel decode failed")
    if diagnostic_protocol:
        if result.get("diagnostic_fixture") is not True:
            raise ValueError("diagnostic provenance differs")
    else:
        if authority is None or site_file is None:
            raise ValueError("reviewed original site authority missing")
        site = json.loads(site_file.read_text(encoding="utf-8"))
        if site.get("reviewed_original_site") is not True:
            raise ValueError("reviewed original site authority missing")
        from signal_trial import construct_plan
        plan = construct_plan(site, authority, case_id.removeprefix(ASSIGNMENT + "__"))
        measured = result.get("measured_values", {})
        for key in ("map_sha256", "device_sha256", "detector_sha256", "blueprint_sha256"):
            if measured.get(key) != plan[key]:
                raise ValueError("reviewed original source changed: " + key)
        if (result.get("provenance_kind") != "native" or
                result.get("diagnostic_fixture") is not False or
                result.get("setup_confirmed") is not True or
                result.get("behavior_attempted") is not True or
                result.get("maneuver_completed") is not True or
                result.get("physical_failure_flags") or
                measured.get("straight_route_observed") is not True or
                not isinstance(measured.get("entry_frame"), int) or
                measured.get("duration_frames") != count):
            raise ValueError("Native physical completion absent")
    return {"format": "c111125-independent-saved-audit-v1", "case_id": case_id,
            "processing_sha256": _sha(receipt_path), "result_sha256": _sha(result_path),
            "joined_frames": count,
            "original_camera_rgb_sha256": {name: value["rgb_sequence_sha256"]
                                           for name, value in decoded.items()},
            "original_frame_map_sha256": mapping_sha,
            "diagnostic_fixture": diagnostic_protocol,
            "software_checks_passed": True, "physical_acceptance": False,
            "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--site", type=Path)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--diagnostic-protocol", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--processed", type=Path)
    args = parser.parse_args()
    if args.processed is None:
        if args.authority_root is None or args.site is None:
            parser.error("source protocol audit requires --authority-root and --site")
        result = audit(args.attempt, args.authority_root, args.site, args.case_id,
                       args.diagnostic_protocol)
    else:
        result = audit_processed(args.attempt, args.processed, args.case_id,
                                 args.diagnostic_protocol, authority=args.authority_root,
                                 site_file=args.site)
    if args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError("independent audit output must remain outside sealed attempt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"case_id": args.case_id,
                      "software_checks_passed": True,
                      "diagnostic_fixture": result["diagnostic_fixture"],
                      "physical_acceptance": False}, sort_keys=True))


if __name__ == "__main__":
    main()

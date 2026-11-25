"""Independently review a sealed bicycle attempt's saved source protocol.

Diagnostic mode tests source joins and all original PNG payloads. It never
produces a canonical physical acceptance receipt. Production review requires
reviewed source authority and a separate canonical video/Core pixel audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_attempt import process_saved
from saved_media_audit import audit_saved_media


ASSIGNMENT = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--diagnostic-protocol", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.attempt, args.authority_root, args.site, args.case_id,
                   args.diagnostic_protocol)
    if args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError("independent audit output must remain outside sealed attempt")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({"case_id": args.case_id,
                      "source_protocol_passed": True,
                      "diagnostic_fixture": result["diagnostic_fixture"],
                      "physical_acceptance": False}, sort_keys=True))


if __name__ == "__main__":
    main()

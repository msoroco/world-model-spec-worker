"""Independent saved-source audit for one C158208 nearest-view attempt.

The production path requires 900 original ticks, the exact reviewed source
hashes, full camera decode, saved measurement, physical traversal, and a
restored Native owner. It leaves visibility quality and legal judgment open.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from camera_sources import audit_camera_sources
from nearest_view_measurement import measure
from physical_completion import assess
from source_tick_capture import verify_seal
from yield_control import KINDS


ASSIGNMENT = "testing__C158208__NRS-484B-257-1__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__" + kind for kind in KINDS}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def audit(attempt: Path, report: Path, *, case_id: str,
          reviewed_expected: dict | None = None,
          diagnostic_fixture: bool = False) -> dict:
    if case_id not in CASES:
        raise ValueError("delivery audit case outside exact nearest-view pair")
    attempt = Path(attempt)
    identity_path = attempt / "capture-identity.json"
    identity = _load(identity_path)
    provenance = "synthetic_fixture" if diagnostic_fixture else "original_capture"
    if identity.get("assignment_id") != ASSIGNMENT or identity.get("case_id") != case_id:
        raise ValueError("exact capture identity case differs")
    if identity.get("provenance_kind") != provenance:
        raise ValueError("original capture provenance differs")
    if not diagnostic_fixture:
        if not isinstance(reviewed_expected, dict):
            raise ValueError("independent reviewed source hashes required")
        for key in ("construction_sha256", "site_packet_sha256", "map_opendrive_sha256"):
            value = reviewed_expected.get(key)
            if not isinstance(value, str) or len(value) != 64 or identity.get(key) != value:
                raise ValueError(f"independent reviewed {key} differs")
    packet = verify_seal(attempt)
    if not diagnostic_fixture and len(packet["samples"]) != 900:
        raise ValueError("original delivery requires 900 contiguous 20 Hz frames")
    media = audit_camera_sources(attempt, diagnostic_fixture=diagnostic_fixture)
    measured = measure(packet)
    saved = _load(report)
    if saved.get("case_id") != case_id or saved.get("diagnostic_fixture") is not diagnostic_fixture:
        raise ValueError("saved measurement case/provenance differs")
    for key, path in (("capture_identity_sha256", identity_path),
                      ("tick_seal_sha256", attempt / "nearest-view-tick-seal.json"),
                      ("packet_sha256", attempt / "nearest-view-saved-packet.json"),
                      ("camera_manifest_sha256", attempt / "nearest-view-camera-manifest.json")):
        if saved.get(key) != _sha(path):
            raise ValueError(f"saved measurement {key} differs from original source")
    if saved.get("measurement") != measured or saved.get("decoded_images") != media["decoded_images"]:
        raise ValueError("saved measurement differs from independently derived original sources")
    completion = assess(attempt, case_id, identity["construction_sha256"],
                        diagnostic_fixture=diagnostic_fixture)
    if not diagnostic_fixture:
        release = _load(attempt / "native-owner-release.json")
        if release.get("case_id") != case_id or release.get("source_kind") != "original_capture":
            raise ValueError("Native owner release case/provenance differs")
        if release.get("frame_count") != 900 or release.get("capture_identity_sha256") != _sha(identity_path):
            raise ValueError("Native owner release source binding differs")
        if release.get("world_restore", {}).get("restored") is not True:
            raise ValueError("Native world restoration not verified")
        if not completion["maneuver_completed"]:
            raise ValueError("original ego body did not complete intersection traversal")
    return {"format": "c158208-independent-delivery-audit-v1", "case_id": case_id,
            "source_kind": provenance, "original_frames": len(packet["samples"]),
            "decoded_camera_images": media["decoded_images"],
            "capture_identity_sha256": _sha(identity_path),
            "saved_report_sha256": _sha(report),
            "checks": {"native_source": True, "all_participants": True,
                       "time_join": True, "original_camera_full_decode": True,
                       "saved_measurement": True,
                       "physical_completion": completion["maneuver_completed"]},
            "physical_acceptance": False, "legal_status": "unresolved",
            "status": "diagnostic_fixture_only" if diagnostic_fixture else "source_bound_pending_visual_review"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--reviewed-expected", type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = _load(args.reviewed_expected) if args.reviewed_expected else None
    result = audit(args.attempt, args.report, case_id=args.case,
                   reviewed_expected=expected,
                   diagnostic_fixture=args.diagnostic_fixture)
    if args.output.exists():
        raise ValueError("independent delivery audit output already exists")
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["status"])

"""Saved-only nearest-view measurement from sealed original ticks and pixels.

The report describes engineering observations. It cannot establish that a sign
was legally governing, the view was adequate, or right of way was yielded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from camera_sources import audit_camera_sources
from nearest_view_measurement import measure
from source_tick_capture import verify_seal


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(attempt: Path, output: Path, *, diagnostic_fixture: bool = False) -> dict:
    attempt = Path(attempt)
    output = Path(output)
    if output.exists():
        raise ValueError("saved measurement already exists")
    packet = verify_seal(attempt)
    media = audit_camera_sources(attempt, diagnostic_fixture=diagnostic_fixture)
    identity_path = attempt / "capture-identity.json"
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("provenance_kind") != ("synthetic_fixture" if diagnostic_fixture else "original_capture"):
        raise ValueError("capture identity provenance differs")
    measured = measure(packet)
    if media["frame_count"] != measured["sample_count"]:
        raise ValueError("camera and measured sample counts differ")
    result = {
        "format": "c158208-nearest-view-saved-report-v1",
        "case_id": identity["case_id"],
        "capture_identity_sha256": _sha(identity_path),
        "tick_seal_sha256": _sha(attempt / "nearest-view-tick-seal.json"),
        "packet_sha256": _sha(attempt / "nearest-view-saved-packet.json"),
        "camera_manifest_sha256": media["camera_manifest_sha256"],
        "measurement": measured,
        "decoded_images": media["decoded_images"],
        "diagnostic_fixture": diagnostic_fixture,
        "physical_acceptance": False,
        "legal_status": "unresolved",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    result = finalize(args.attempt, args.output, diagnostic_fixture=args.diagnostic_fixture)
    print(json.dumps({"case_id": result["case_id"], "sample_count": result["measurement"]["sample_count"],
                      "decoded_images": result["decoded_images"], "legal_status": result["legal_status"]}))

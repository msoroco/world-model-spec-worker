"""Independent saved-source audit for a planned flashing-arrow delivery.

A passing software audit does not establish original Native physical acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_camera_capture import CAMERAS
from saved_aspect import join_event_history
from saved_camera_audit import audit as audit_cameras
from saved_finalizer import ASSIGNMENT, SUFFIXES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt: Path, case_id: str, *, diagnostic=False, dimensions=None):
    attempt = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in SUFFIXES}:
        raise ValueError("unknown exact flashing-arrow delivery case")
    config = json.loads((attempt / "config.json").read_text())
    if config.get("selected_case_id") != case_id or config.get("cameras") != list(CAMERAS):
        raise ValueError("saved delivery config selects another case or camera inventory")
    site_path = attempt / "site.json"
    if not site_path.is_file():
        raise ValueError("saved delivery site source missing")
    site = json.loads(site_path.read_text())
    if site.get("case_id") != case_id:
        raise ValueError("saved delivery site selects another case")
    if not diagnostic and site.get("source_kind") != "original_native_site_review":
        raise ValueError("reviewed original Native site required for delivery")
    event_receipt = json.loads((attempt / "arrow-event-receipt.json").read_text())
    if event_receipt.get("diagnostic") is not diagnostic:
        raise ValueError("diagnostic actor event receipt cannot prove delivery")
    joined = join_event_history(site, attempt, event_receipt["event_ref"],
                                delivery=not diagnostic)
    camera = audit_cameras(site, attempt, diagnostic=diagnostic,
                           dimensions=dimensions)
    if (joined["original_event_sha256"] != camera["original_event_sha256"] or
            joined["original_aspect_sha256"] != camera["original_aspect_sha256"] or
            joined["frame_count"] != camera["decoded_frames"] or
            camera["decoded_images"] != 4 * joined["frame_count"]):
        raise ValueError("independent actor/aspect/camera source join differs")
    if not diagnostic and joined["frame_count"] != 900:
        raise ValueError("production delivery lacks 900 original frames")
    result = {"format": "c111610-independent-saved-source-audit-v1",
              "case_id": case_id, "software_source_checks_passed": True,
              "site_sha256": sha(site_path),
              "aspect_sha256": joined["original_aspect_sha256"],
              "event_sha256": joined["original_event_sha256"],
              "camera_receipt_sha256": sha(attempt / "arrow-camera-receipt.json"),
              "frame_count": joined["frame_count"],
              "decoded_images": camera["decoded_images"],
              "physical_acceptance": False, "legal_verdict": None,
              "diagnostic": diagnostic}
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--diagnostic-width", type=int)
    parser.add_argument("--diagnostic-height", type=int)
    args = parser.parse_args()
    dimensions = None
    if args.diagnostic:
        if not args.diagnostic_width or not args.diagnostic_height:
            raise ValueError("diagnostic dimensions required")
        dimensions = {name: (args.diagnostic_width, args.diagnostic_height)
                      for name in CAMERAS}
    elif args.diagnostic_width or args.diagnostic_height:
        raise ValueError("diagnostic dimensions cannot be used in delivery")
    print(json.dumps(audit(args.attempt, args.case,
                           diagnostic=args.diagnostic, dimensions=dimensions),
                     indent=2))


if __name__ == "__main__":
    main()

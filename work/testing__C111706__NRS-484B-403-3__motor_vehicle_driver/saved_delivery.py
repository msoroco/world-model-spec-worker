"""Saved-only source audit for the three exact intersection U-turn cases.

The output measures recorded reversal and intersection occupancy without
deciding whether the district or intersection has the statutory classification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_uturn import analyze_native
from saved_cameras import audit as audit_cameras


ASSIGNMENT = "testing__C111706__NRS-484B-403-3__motor_vehicle_driver"
CASES = {ASSIGNMENT + "__" + suffix for suffix in (
    "intersection_vehicle_near", "approach_before_intersection",
    "intersection_vehicle_far")}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_saved(native_path: Path, camera_manifest: Path, site_path: Path,
                case_id: str, *, diagnostic: bool = False,
                expected_views=None) -> dict:
    """Require exact source joins and observed location separation.

    ``diagnostic`` permits only the three-frame small-camera CPU fixture.
    Original mode requires all 900 20 Hz frames and the capture profile.
    """
    if case_id not in CASES:
        raise ValueError("unknown exact U-turn case")
    native_path = Path(native_path)
    camera_manifest = Path(camera_manifest)
    site_path = Path(site_path)
    packet = json.loads(native_path.read_text())
    site = json.loads(site_path.read_text())
    if packet.get("case_id") != case_id or site.get("case_id") != case_id:
        raise ValueError("saved Native/site exact case differs")
    if packet.get("site_sha256") != _sha(site_path):
        raise ValueError("saved Native/site source binding differs")
    if (packet.get("map_sha256") != site.get("map_sha256") or
            packet.get("route_sha256") != site.get("route_sha256") or
            packet.get("district_basis", {}).get("source_sha256") != site.get("district_source_sha256") or
            packet.get("intersection_boundary") != site.get("intersection_boundary")):
        raise ValueError("saved Native reviewed map, route, district or boundary differs")
    if not diagnostic and site.get("source_kind") != "original_native_site_review":
        raise ValueError("original reviewed Native site required")
    measured = analyze_native(native_path, expected_case=case_id,
                              expected_sha256=_sha(native_path))
    count = 3 if diagnostic else 900
    if measured["frame_count"] != count:
        raise ValueError("exact 20 Hz source frame count differs")
    frames = packet["frames"]
    if any(abs(b["time_s"] - a["time_s"] - .05) > .001
           for a, b in zip(frames, frames[1:])):
        raise ValueError("original Native 20 Hz cadence differs")
    inside = bool(measured["whole_body_inside_intersection_frames"])
    expected_inside = not case_id.endswith("__approach_before_intersection")
    if inside != expected_inside:
        raise ValueError("measured U-turn location differs from exact case")
    camera = audit_cameras(native_path, _sha(native_path), camera_manifest,
                           _sha(camera_manifest), expected_case=case_id,
                           expected_count=count, expected_views=expected_views)
    if camera["native_sha256"] != measured["source_sha256"]:
        raise ValueError("camera and motion audits use different Native source")
    return {"format": "c111706-saved-delivery-source-audit-v1",
            "case_id": case_id, "source_kind": site.get("source_kind", "diagnostic_fixture"),
            "site_sha256": _sha(site_path), "native_sha256": measured["source_sha256"],
            "camera_manifest_sha256": camera["camera_manifest_sha256"],
            "original_frame_count": count,
            "measured_reversal_deg": measured["reversal_deg"],
            "whole_body_inside_intersection_frames":
                measured["whole_body_inside_intersection_frames"],
            "minimum_other_vehicle_center_distance_m":
                measured["minimum_other_vehicle_center_distance_m"],
            "decoded_camera_sources": camera["source_decode"],
            "checks": {"native_source": not diagnostic,
                       "all_participants": True, "time_join": True,
                       "full_video_decode": False, "actual_pixels": False,
                       "physical_completion": False},
            "district_classification": "unresolved_review",
            "physical_acceptance": "not_assessed",
            "legal_judgment": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--camera-manifest", type=Path, required=True)
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit_saved(args.native, args.camera_manifest, args.site,
                                  args.case, diagnostic=args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()

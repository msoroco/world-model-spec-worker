"""Saved-only original Native sign and bicycle roadway-use measurement."""
from __future__ import annotations

import hashlib
import json
import math

from native_site import canonical_sha, validate_site


def measure(site: dict, packet: dict, case: dict) -> dict:
    binding = validate_site(site)
    diagnostic = packet.get('source_kind') == 'diagnostic_fixture_capture'
    if packet.get("source_kind") not in ('original_native_capture', 'diagnostic_fixture_capture') or packet.get("site_sha256") != binding["site_sha256"]:
        raise ValueError("missing or mismatched original Native site source")
    body = {key: value for key, value in packet.items() if key != "seal_sha256"}
    if packet.get("seal_sha256") != canonical_sha(body):
        raise ValueError("original Native capture seal mismatch")
    if packet.get("case_id") != case.get("case_id") or packet.get("actor_blueprint_id") != site["bicycle_blueprint_id"]:
        raise ValueError("case or bicycle identity mismatch")
    if packet.get("map_name") != site["map_name"] or packet.get("street_id") != site["street_id"]:
        raise ValueError("map or street identity mismatch")
    frames = packet.get("frames")
    if not isinstance(frames, list) or len(frames) != 900:
        raise ValueError("45-second 20-Hz original frame history required")
    sign = site["sign"]
    roadway_frames = []
    trail_frames = []
    last_time = -math.inf
    for index, row in enumerate(frames):
        if row.get("original_frame") != index or row.get("actor_id") != packet.get("actor_id"):
            raise ValueError("original frame or actor continuity failure")
        t = row.get("elapsed_s")
        if not isinstance(t, (int, float)) or not math.isfinite(t) or t <= last_time or abs(t - index / 20) > 0.001:
            raise ValueError("original 20-Hz time continuity failure")
        last_time = t
        if row.get("sign_source_id") != sign["source_id"] or row.get("sign_posted_readback") is not True:
            raise ValueError("original sign readback missing")
        if row.get("segment") not in ("nonmotorized_trail", "governed_street_roadway"):
            raise ValueError("original route segment missing")
        if row.get("street_id") != site["street_id"]:
            raise ValueError("governed street readback mismatch")
        if row["segment"] == "governed_street_roadway":
            roadway_frames.append(index)
        else:
            trail_frames.append(index)
    if case.get("motion") == "enter_roadway" and (not trail_frames or not roadway_frames or min(roadway_frames) < min(trail_frames)):
        raise ValueError("roadway entry not observed after trail")
    if case.get("motion") in ("remain_trail", "stop_before_roadway") and roadway_frames:
        raise ValueError("roadway entry contradicts planned nonentry")
    return {"source_kind": "diagnostic_fixture_measurement" if diagnostic else "original_native_measurement", "case_id": case["case_id"], "site_sha256": binding["site_sha256"], "packet_sha256": hashlib.sha256(json.dumps(packet, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "frames": len(frames), "roadway_frames": len(roadway_frames), "trail_frames": len(trail_frames), "first_roadway_frame": min(roadway_frames) if roadway_frames else None, "sign_posted_original_frames": len(frames), "designation_source": site["engineer_designation_source"], "legal_assessment": "unresolved"}

"""Independent saved-source checks for a later physical delivery attempt.

This checks packet completeness and source identity; it cannot establish that
the crosswalk was physically practicable or that pixels are readable.
"""
from __future__ import annotations

import hashlib
from pathlib import Path


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _file_hash(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("missing saved source: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_saved(packet, measurement, source_root):
    if packet.get("case_id") != measurement.get("case_id"):
        raise ValueError("case identity differs")
    if not packet.get("native_result_sha256") or not packet.get("frame_map_sha256"):
        raise ValueError("unsealed Native result or frame map")
    if packet.get("fps") != 20 or packet.get("frame_count", 0) < 2:
        raise ValueError("invalid original frame profile")
    if measurement.get("legal_practicability") != "unresolved":
        raise ValueError("unsupported practicability verdict")
    trace = measurement.get("full_original_trace")
    if not isinstance(trace, list) or len(trace) != packet["frame_count"]:
        raise ValueError("missing full original pedestrian trace")
    frames = [row.get("frame") for row in trace]
    if frames != list(range(frames[0], frames[0] + len(frames))):
        raise ValueError("gapped original frame map")
    if not any(row.get("within_crosswalk") for row in trace):
        raise ValueError("no observed crosswalk passage")
    for row in trace:
        if row.get("obstacle_source") != measurement["fixed_sources"].get("obstacle_source_sha256"):
            raise ValueError("missing original obstacle join")
        if row.get("participant_source") != measurement["fixed_sources"].get("participant_source_sha256"):
            raise ValueError("missing original participant join")
        if row.get("available_right_width_m") is None or row.get("nearby_participants") is None:
            raise ValueError("missing practicability context")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("missing sealed saved sources")
    actual = {}
    for key in ("native_result", "frame_map", *CAMERAS):
        item = sources.get(key)
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            raise ValueError("missing saved source: " + key)
        path = (Path(source_root) / item["path"]).resolve()
        if not path.is_relative_to(Path(source_root).resolve()):
            raise ValueError("saved source escapes attempt")
        digest = _file_hash(path)
        if digest != item["sha256"]:
            raise ValueError("saved source hash differs: " + key)
        actual[key] = digest
    if actual["native_result"] != packet["native_result_sha256"]:
        raise ValueError("Native result binding differs")
    if actual["frame_map"] != packet["frame_map_sha256"]:
        raise ValueError("frame map binding differs")
    return {"passed": True, "case_id": packet["case_id"],
            "frame_count": packet["frame_count"], "source_sha256": actual,
            "physical_visibility": "unverified", "legal_practicability": "unresolved"}

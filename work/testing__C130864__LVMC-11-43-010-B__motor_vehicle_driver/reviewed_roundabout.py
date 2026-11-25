"""Validate an original reviewed Native roundabout source packet before launch."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from capture_roundabout import CAMERAS
from native_roundabout import load_case


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed(path, expected_case_id):
    review_path = Path(path).resolve()
    review = json.loads(review_path.read_text())
    if review.get("case_id") != expected_case_id or review.get("review_status") != "reviewed_original":
        raise ValueError("exact original roundabout source review required")
    refs = review.get("sources")
    if not isinstance(refs, dict) or set(refs) != {"opendrive", "construction_packet", "camera_placement"}:
        raise ValueError("original roundabout source inventory incomplete")
    sources = {}
    for name, ref in refs.items():
        source = Path(ref["path"])
        if not source.is_absolute():
            source = review_path.parent / source
        source = source.resolve()
        if not source.is_file() or _sha(source) != ref.get("sha256"):
            raise ValueError("review source changed before Native launch: " + name)
        sources[name] = source
    packet = load_case(sources["construction_packet"], refs["construction_packet"]["sha256"],
                       expected_case_id)
    if _sha(sources["opendrive"]) != packet["map_sha256"]:
        raise ValueError("reviewed original OpenDRIVE does not match map packet")
    placement = json.loads(sources["camera_placement"].read_text())
    if set(placement.get("cameras", {})) != set(CAMERAS):
        raise ValueError("four original camera placements required")
    for name in CAMERAS:
        row = placement["cameras"][name]
        for key in ("location_xyz_m", "pitch_yaw_roll_deg"):
            values = row.get(key)
            if not isinstance(values, list) or len(values) != 3 or not all(
                    type(value) in (int, float) for value in values):
                raise ValueError("original camera pose missing: " + name)
    return {"review_sha256": _sha(review_path), "sources": sources,
            "packet": packet, "placement": placement}

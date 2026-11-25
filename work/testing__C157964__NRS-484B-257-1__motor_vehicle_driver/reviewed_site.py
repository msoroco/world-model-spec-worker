"""Verify reviewed original site bytes before a C157964 Native operation.

This is a source custody boundary. A diagnostic packet can test this code but
cannot establish that a real yield sign or nearest-view point exists.
"""

import hashlib
import json
from pathlib import Path

from yield_view import validate_site


SITE_ROLES = (
    "jurisdiction", "yield_sign", "stop_line_absence", "crosswalk_absence",
    "nearest_view_location", "through_highway", "sight_observation",
    "officer_control", "traffic_signal_control", "ego_vehicle",
)
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("source path must be relative")
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("reviewed source path escapes or is missing")
    return target


def read_reviewed_site(packet_path, source_root, case):
    """Return a verified site and packet hash; reject changed source bytes."""
    root = Path(source_root).resolve()
    packet_file = Path(packet_path).resolve()
    if not packet_file.is_relative_to(root) or not packet_file.is_file():
        raise ValueError("reviewed packet is outside source root")
    packet_bytes = packet_file.read_bytes()
    packet = json.loads(packet_bytes)
    if packet.get("format") != "c157964-reviewed-yield-site-v1":
        raise ValueError("reviewed site format differs")
    if packet.get("provenance") != "reviewed_original":
        raise ValueError("diagnostic site cannot be an original source")
    if packet.get("case_id") != case.case_id:
        raise ValueError("reviewed packet case differs")
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(SITE_ROLES):
        raise ValueError("reviewed site source roles differ")
    site = packet.get("site")
    if not isinstance(site, dict):
        raise ValueError("reviewed site record missing")
    for role in SITE_ROLES:
        ref = sources[role]
        if not isinstance(ref, dict):
            raise ValueError("reviewed source reference missing: " + role)
        path = _inside(root, ref.get("path"))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if ref.get("sha256") != digest or site.get(role + "_source_sha256") != digest:
            raise ValueError("reviewed source bytes changed: " + role)
    dimensions = site.get("camera_dimensions")
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError("four-camera dimensions missing")
    for view in CAMERAS:
        size = dimensions[view]
        if (not isinstance(size, list) or len(size) != 2 or
                any(type(value) is not int or value <= 0 for value in size)):
            raise ValueError("camera dimensions invalid: " + view)
    validate_site(site, case)
    return site, hashlib.sha256(packet_bytes).hexdigest()

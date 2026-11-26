"""Require a locally reviewed, byte-bound original curb and assembly packet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from projection_construction import CASES, curb_frame
from projection_measurement import ASSIGNMENT

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reviewed(path, case_id):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("original reviewed source packet missing")
    packet = json.loads(path.read_text(encoding="utf-8"))
    site = packet.get("site")
    if (packet.get("format") != "c150088-original-site-v1" or
            packet.get("assignment_id") != ASSIGNMENT or
            case_id not in [case.case_id for case in CASES] or
            not isinstance(site, dict) or not isinstance(packet.get("sources"), dict)):
        raise ValueError("exact reviewed projection source binding required")
    if not packet.get("reviewer") or not packet.get("review_citation"):
        raise ValueError("independent original source review required")
    if not site.get("reviewer") or site["reviewer"] != packet["reviewer"]:
        raise ValueError("reviewed curb source identity differs")
    curb_frame(site)
    for name in ("vehicle_blueprint", "load_blueprint", "trailer_blueprint",
                 "street_jurisdiction", "one_way_direction_source"):
        if not site.get(name):
            raise ValueError("original site field missing: " + name)
    required = {"opendrive", "curb_survey", "vehicle_dimensions",
                "load_dimensions", "trailer_dimensions"}
    if not required <= set(packet["sources"]):
        raise ValueError("original map, curb and all part dimensions required")
    for name, entry in packet["sources"].items():
        if not isinstance(entry, dict) or not entry.get("citation") or not entry.get("reviewer"):
            raise ValueError("original source review missing: " + name)
        relative = Path(entry.get("path", ""))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError("reviewed relative source path required")
        source = path.parent / relative
        if not source.is_file() or source.is_symlink() or sha(source) != entry.get("sha256"):
            raise ValueError("original source byte binding differs: " + name)
    if site["opendrive_sha256"] != packet["sources"]["opendrive"]["sha256"]:
        raise ValueError("reviewed OpenDRIVE identity differs")
    camera = packet.get("camera_plan")
    if (not isinstance(camera, dict) or set(camera) != set(CAMERAS) or
            any(not isinstance(camera[name], dict) or
                    not camera[name].get("source_transform") or
                    not camera[name].get("purpose") for name in CAMERAS)):
        raise ValueError("four original camera placement sources required")
    return packet, site


def validate_native_adapter(packet, module_path):
    module_path = Path(module_path)
    binding = packet.get("native_adapter")
    if (not module_path.is_file() or module_path.is_symlink() or
            not isinstance(binding, dict) or binding.get("sha256") != sha(module_path) or
            not binding.get("citation") or not binding.get("reviewer")):
        raise ValueError("hash-bound reviewed original Native adapter required")
    return module_path

"""Reopen reviewed original bus, curb, location and loading sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from bus_curb import CASES, construct, measure_original, validate_scene

FIELDS = ("jurisdiction", "bus_class", "tour_exclusion", "operator",
          "location_boundary", "location_designation", "signs", "curb_geometry",
          "right_front_wheel", "bus_route", "loading_activity", "traffic_route")
FRAME_FIELDS = ("right_front_wheel", "curb_geometry", "location_designation",
                "loading_activity")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, case_name: str) -> dict:
    packet_path = Path(packet_path)
    if packet_path.is_symlink() or not packet_path.is_file():
        raise ValueError("original reviewed bus site packet missing")
    packet_path = packet_path.resolve()
    packet = json.loads(packet_path.read_text())
    if (packet.get("format") != "c149470-reviewed-site-v1"
            or packet.get("review_status") != "reviewed"
            or packet.get("diagnostic_fixture") is True
            or not packet.get("reviewer")):
        raise ValueError("original reviewed bus site missing")
    matches = [case for case in CASES if case.name == case_name]
    if len(matches) != 1:
        raise ValueError("unknown exact bus case")
    scene = packet.get("scene")
    if not isinstance(scene, dict):
        raise ValueError("reviewed bus scene missing")
    if (scene.get("case_id") != "testing__C149470__LVMC-11-60-030-A4__bus_driver__" + case_name
            or scene.get("source_kind") != "original_reviewed_site"
            or scene.get("diagnostic_fixture") is True):
        raise ValueError("reviewed bus scene identity or provenance missing")
    validate_scene(scene, matches[0])
    bindings = packet.get("source_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(FIELDS):
        raise ValueError("original bus source inventory incomplete")
    for name, item in bindings.items():
        if not isinstance(item, dict) or not item.get("citation") or not item.get("reviewer"):
            raise ValueError("original bus source citation missing: " + name)
        rel = item.get("path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("original bus source path invalid: " + name)
        path = packet_path.parent / rel
        if (path.is_symlink() or not path.is_file() or
                not path.resolve().is_relative_to(packet_path.parent) or
                sha(path) != item.get("sha256") or
                scene[name + "_source_sha256"] != item["sha256"]):
            raise ValueError("original bus source bytes missing or changed: " + name)
    return {"case_name": case_name, "site_sha256": sha(packet_path),
            "source_hashes": {name: item["sha256"] for name, item in bindings.items()},
            "scene": scene, "legal_judgment": "unresolved"}


def construct_reviewed(adapter, packet_path: Path, case_name: str) -> dict:
    reviewed = verify(packet_path, case_name)
    case = next(case for case in CASES if case.name == case_name)
    result = construct(adapter, reviewed["scene"], case)
    result["site_sha256"] = reviewed["site_sha256"]
    result["source_hashes"] = reviewed["source_hashes"]
    return result


def measure_reviewed(rows: list[dict], packet_path: Path, case_name: str) -> dict:
    reviewed = verify(packet_path, case_name)
    for row in rows:
        if any(row.get(name + "_source_sha256") != reviewed["source_hashes"][name]
               for name in FRAME_FIELDS):
            raise ValueError("original bus frame context differs from reviewed source")
    case = next(case for case in CASES if case.name == case_name)
    result = measure_original(rows, reviewed["scene"], case)
    result["site_sha256"] = reviewed["site_sha256"]
    result["source_hashes"] = reviewed["source_hashes"]
    return result

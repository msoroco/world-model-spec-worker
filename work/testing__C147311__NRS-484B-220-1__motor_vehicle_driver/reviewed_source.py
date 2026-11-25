"""Reopen original C147311 site sources before production construction or measurement."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_direction import CASES, construct, measure_original, validate_scene

FIELDS = ("highway", "vehicle", "driver_control", "lane_inventory",
          "one_way_designation", "sign_authority", "sign_message",
          "sign_orientation", "sign_placement", "sign_governance", "ego_route")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, case_name: str) -> dict:
    packet_path = Path(packet_path)
    if packet_path.is_symlink() or not packet_path.is_file():
        raise ValueError("original reviewed site packet missing")
    packet_path = packet_path.resolve()
    packet = json.loads(packet_path.read_text())
    if (packet.get("format") != "c147311-reviewed-site-v1"
            or packet.get("review_status") != "reviewed"
            or packet.get("diagnostic_fixture") is True
            or not packet.get("reviewer")):
        raise ValueError("original reviewed C147311 site missing")
    matches = [case for case in CASES if case.name == case_name]
    if len(matches) != 1:
        raise ValueError("unknown exact one-way case")
    case = matches[0]
    scene = packet.get("scene")
    if not isinstance(scene, dict):
        raise ValueError("reviewed scene missing")
    validate_scene(scene, case)
    bindings = packet.get("source_bindings")
    if not isinstance(bindings, dict) or set(bindings) != set(FIELDS):
        raise ValueError("original source inventory incomplete")
    root = packet_path.parent
    for name, item in bindings.items():
        if not isinstance(item, dict) or not item.get("citation") or not item.get("reviewer"):
            raise ValueError("original source citation missing: " + name)
        rel = item.get("path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("original source path invalid: " + name)
        path = root / rel
        if (path.is_symlink() or not path.is_file() or
                not path.resolve().is_relative_to(root) or
                sha(path) != item.get("sha256") or
                scene[name + "_source_sha256"] != item["sha256"]):
            raise ValueError("original source bytes missing or changed: " + name)
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
    case = next(case for case in CASES if case.name == case_name)
    bound = ("driver_control", "lane_inventory", "one_way_designation",
             "sign_authority", "sign_message", "sign_orientation", "sign_governance")
    for row in rows:
        if any(row.get(name + "_source_sha256") != reviewed["source_hashes"][name]
               for name in bound):
            raise ValueError("original frame context differs from reviewed source")
    result = measure_original(rows, reviewed["scene"], case)
    result["site_sha256"] = reviewed["site_sha256"]
    result["source_hashes"] = reviewed["source_hashes"]
    return result

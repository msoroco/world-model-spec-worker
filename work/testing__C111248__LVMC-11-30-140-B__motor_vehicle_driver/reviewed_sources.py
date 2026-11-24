"""Bind reviewed original sources to an exact blind-person Native plan.

The reviewer supplies three independent JSON files and their SHA256 values.
No simulator state or diagnostic fixture can establish blindness by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT_ID = "testing__C111248__LVMC-11-30-140-B__motor_vehicle_driver"
spec = importlib.util.spec_from_file_location("blind_encounter_reviewed", HERE / "blind_encounter.py")
encounter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = encounter
spec.loader.exec_module(encounter)


def _read(root: Path, entry: dict, label: str) -> tuple[Path, dict, str]:
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError(f"missing {label} path")
    raw_path = root / entry["path"]
    path = raw_path.resolve()
    if raw_path.is_symlink() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"missing or escaping {label} file")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if entry.get("sha256") != digest:
        raise ValueError(f"{label} SHA256 mismatch")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a JSON object")
    return path, data, digest


def prepare(packet_path: Path) -> dict:
    """Validate an exact reviewed packet, returning a source-bound Native plan."""
    packet_path = packet_path.resolve(strict=True)
    root = packet_path.parent
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    if packet.get("assignment_id") != ASSIGNMENT_ID:
        raise ValueError("assignment identity mismatch")
    case_id = packet.get("case_id")
    if case_id not in encounter.CASE_BY_ID:
        raise ValueError("exact case identity mismatch")
    map_path, map_data, map_hash = _read(root, packet.get("reviewed_map_route"), "reviewed map route")
    att_path, att, att_hash = _read(root, packet.get("blindness_attestation"), "blindness attestation")
    cue_path, cue, cue_hash = _read(root, packet.get("carried_cue"), "carried cue")
    if len({map_path, att_path, cue_path}) != 3:
        raise ValueError("reviewed sources must be distinct files")
    if map_data.get("reviewed_from") != "original_native_map" or not map_data.get("reviewer"):
        raise ValueError("original Native map review required")
    if att.get("basis") not in ("wholly_blind", "partially_blind") or not att.get("issuer"):
        raise ValueError("independent blindness basis and issuer required")
    if cue.get("observation") != "actually_carried" or not cue.get("observer_source"):
        raise ValueError("observed carried cue source required")
    # Metadata names its original evidence separately; a file cannot contain
    # its own SHA256. Both originals must exist and match those declared hashes.
    att_original, _, att_original_hash = _read(root, att.get("original_source"), "blindness original")
    cue_original, _, cue_original_hash = _read(root, cue.get("original_source"), "cue original")
    if len({map_path, att_path, cue_path, att_original, cue_original}) != 5:
        raise ValueError("original evidence files must be independent")
    if att.get("source_sha256") != att_original_hash or cue.get("source_sha256") != cue_original_hash:
        raise ValueError("original evidence provenance mismatch")
    if any(not isinstance(map_data.get(name), int) or isinstance(map_data.get(name), bool)
           for name in ("driver_actor_id", "pedestrian_actor_id")):
        raise ValueError("reviewed actor identities required")
    plan = encounter.plan_native(
        case_id, map_id=map_data.get("map_id"),
        route_waypoints=map_data.get("route_waypoints", []),
        pedestrian_pose=map_data.get("pedestrian_pose", {}),
        blindness_attestation=att, cue_source=cue,
        driver_actor_id=map_data.get("driver_actor_id"),
        pedestrian_actor_id=map_data.get("pedestrian_actor_id"),
    )
    for waypoint in plan["route_waypoints"]:
        if not all(isinstance(waypoint[k], (int, float)) and math.isfinite(waypoint[k]) for k in ("x", "y")):
            raise ValueError("nonfinite map route")
    plan["reviewed_source_bindings"] = {
        "reviewed_map_route": map_hash,
        "blindness_attestation": att_hash,
        "carried_cue": cue_hash,
        "blindness_original": att_original_hash,
        "cue_original": cue_original_hash,
        "packet": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
    }
    plan["physical_acceptance_claimed"] = False
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    plan = prepare(args.packet)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(plan, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()

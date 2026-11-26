"""Verify original sidewalk-elevator site sources before exact-case expansion.

This is a source custody step. It does not establish fixture visibility or a
legal stopping outcome; those require an original Native capture and review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking import CASES, target_body_interval, validate_site


BASE_SOURCES = (
    "map", "municipal_jurisdiction", "sidewalk", "fixture_identity",
    "fixture_geometry", "curb", "one_way_direction", "fixture_blueprint",
    "ego_blueprint", "camera_plan", "activity_purpose", "occupancy",
    "responsible_person", "vehicle_definitions",
)
EXCEPTION_SOURCE = {
    "lawful_traffic_conflict": "traffic_conflict_source",
    "police_direction": "police_direction_source",
    "traffic_device_direction": "traffic_device_source",
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, source_root: Path) -> dict:
    packet_path = Path(packet_path)
    source_root = Path(source_root).resolve()
    packet = json.loads(packet_path.read_text())
    site = packet.get("site", {})
    validate_site(site)
    if packet.get("assignment_id") != "testing__C150153__LVMC-11-52-130-A5__motor_vehicle_driver":
        raise ValueError("reviewed site assignment mismatch")
    if not packet.get("reviewer") or not packet.get("citation"):
        raise ValueError("reviewed site author or citation missing")
    sources = packet.get("sources")
    if not isinstance(sources, dict):
        raise ValueError("reviewed site source inventory missing")
    required = set(BASE_SOURCES) | set(EXCEPTION_SOURCE.values())
    if set(sources) != required:
        raise ValueError("reviewed site source inventory incomplete")
    for key, item in sources.items():
        if not isinstance(item, dict) or not item.get("reviewer") or not item.get("citation"):
            raise ValueError("original source review missing: " + key)
        relative = Path(item.get("path", ""))
        if relative.is_absolute() or not relative.parts or ".." in relative.parts:
            raise ValueError("original source path escapes root: " + key)
        path = (source_root / relative).resolve()
        if not path.is_relative_to(source_root) or not path.is_file() or not path.read_bytes():
            raise ValueError("original source absent or empty: " + key)
        digest = _sha(path)
        if item.get("sha256") != digest or site.get(key + "_sha256") != digest:
            raise ValueError("original source hash differs: " + key)
    return packet


def exact_specs(packet_path: Path, source_root: Path, body_length_m: float) -> dict:
    packet = verify(packet_path, source_root)
    site = packet["site"]
    specs = []
    for case in CASES:
        interval = target_body_interval(site, case, body_length_m)
        specs.append({
            "case_id": packet["assignment_id"] + "__" + case.id,
            "region": case.region,
            "activity": case.activity,
            "exception": case.exception,
            "commanded_body_interval_m": list(interval),
            "physical_risk": "Native fixture placement, route and body geometry require original review",
            "site_packet_sha256": _sha(Path(packet_path)),
            "capture_frames": 900,
            "capture_rate_hz": 20,
        })
    return {"format": "reviewed-sidewalk-elevator-exact-specs", "status": "source_bound_unproven",
            "assignment_id": packet["assignment_id"], "cases": specs}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--body-length-m", type=float, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to((Path.cwd() / ".runtime-work").resolve()):
        raise ValueError("case specs output must be under .runtime-work")
    if args.output.exists():
        raise ValueError("case specs output already exists")
    specs = exact_specs(args.packet, args.source_root, args.body_length_m)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(specs, indent=2) + "\n")


if __name__ == "__main__":
    main()

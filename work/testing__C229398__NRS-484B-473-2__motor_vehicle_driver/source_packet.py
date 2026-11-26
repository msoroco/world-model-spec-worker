"""Verify reviewed parked-lamp, lawful-parking, nighttime and site sources."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parked_lamps import CASES, SCENE_SOURCES, validate_scene


ASSIGNMENT = "testing__C229398__NRS-484B-473-2__motor_vehicle_driver"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, *, diagnostic_fixture: bool = False) -> dict:
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    case_id = packet.get("case_id")
    case_by_id = {ASSIGNMENT + "__" + case.name: case for case in CASES}
    if packet.get("assignment_id") != ASSIGNMENT or case_id not in case_by_id:
        raise ValueError("exact assignment or case identity differs")
    expected_kind = "synthetic_fixture" if diagnostic_fixture else "original_reviewed"
    if packet.get("source_kind") != expected_kind:
        raise ValueError("source provenance differs")
    if not diagnostic_fixture and packet.get("review_status") != "reviewed":
        raise ValueError("original site packet has not been reviewed")
    scene = packet.get("scene")
    if not isinstance(scene, dict):
        raise ValueError("scene missing")
    validate_scene(scene, case_by_id[case_id])
    refs = packet.get("source_refs")
    required = set(SCENE_SOURCES) | {"map_opendrive"}
    if not isinstance(refs, dict) or set(refs) != required:
        raise ValueError("independent source inventory differs")
    if not isinstance(scene.get("map_opendrive_sha256"), str):
        raise ValueError("source-bound map hash missing")
    for name in sorted(required):
        ref = refs[name]
        if not isinstance(ref, dict):
            raise ValueError("source binding invalid: " + name)
        rel = ref.get("path")
        if (not isinstance(rel, str) or not rel or Path(rel).name != rel or
                rel in (".", "..")):
            raise ValueError("source path must be adjacent: " + name)
        source = packet_path.parent / rel
        digest = ref.get("sha256")
        if (not isinstance(digest, str) or len(digest) != 64 or
                not source.is_file() or sha(source) != digest):
            raise ValueError("source bytes missing or changed: " + name)
        if (not isinstance(ref.get("observation"), str) or
                not ref["observation"].strip()):
            raise ValueError("source observation missing: " + name)
        bound = (scene.get("map_opendrive_sha256") if name == "map_opendrive" else
                 scene.get(name + "_source_sha256"))
        if bound != digest:
            raise ValueError("scene/source hash differs: " + name)
        if not diagnostic_fixture and ref.get("review_status") != "reviewed":
            raise ValueError("original source has not been reviewed: " + name)
    return {"case_id": case_id, "packet_sha256": sha(packet_path),
            "source_kind": expected_kind,
            "source_hashes": {name: refs[name]["sha256"] for name in sorted(required)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(verify(args.packet, diagnostic_fixture=args.diagnostic_fixture),
                     sort_keys=True))

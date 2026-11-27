"""Hash-bound original source review for emergency-unit Native construction."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from emergency_construction import CASES, plan

AID = "testing__C404479__NRS-484B-267-2d__motor_vehicle_driver"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_packet(path: str | Path, case_id: str) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("reviewed original packet file required")
    packet = json.loads(path.read_text(encoding="utf-8"))
    cases = {AID + "__" + case.suffix: case for case in CASES}
    if case_id not in cases or packet.get("case_id") != case_id:
        raise ValueError("exact case identity mismatch")
    if packet.get("source_kind") != "reviewed_native_emergency_approach_2d_sources":
        raise ValueError("reviewed Native packet source kind required")
    sources = packet.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ValueError("reviewed source inventory required")
    for source in sources:
        item = Path(source.get("path", ""))
        if (not item.is_file() or item.is_symlink() or not source.get("reviewer")
                or not source.get("citation") or source.get("sha256") != sha(item)):
            raise ValueError("source hash/reviewer/citation mismatch")
    for key in ("map_source", "actor_source", "authority"):
        if not isinstance(packet.get(key), dict):
            raise ValueError(key + " original source required")
    plan(cases[case_id], packet["map_source"], packet["actor_source"], packet["authority"])
    cameras = packet.get("cameras")
    if not isinstance(cameras, list) or [view.get("name") for view in cameras] != list(VIEWS):
        raise ValueError("four reviewed camera views required")
    for view in cameras:
        if not view.get("native_pose") or not view.get("reviewer") or not view.get("source_ref"):
            raise ValueError("reviewed Native camera pose required")
    return packet

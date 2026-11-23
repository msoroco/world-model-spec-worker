"""Saved-only branch evidence audit for NRS 484B.560(3).

The statutory right-side duty stays separate from the marked-lane qualification.
This is an evidence sufficiency audit, never a legal finding.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


REQUIRED = ("stop_authority", "highway_boundary", "lane_markings",
            "vehicle_footprints", "right_side_constraints", "stop_episode")


def audit(packet_path: Path) -> dict:
    packet_path = Path(packet_path)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    sources = packet.get("sources")
    if not isinstance(sources, dict) or set(sources) != set(REQUIRED):
        raise ValueError("all six original crossing evidence sources required")
    verified = {}
    for name in REQUIRED:
        spec = sources[name]
        if not isinstance(spec, dict) or not spec.get("path") or not spec.get("sha256"):
            raise ValueError("missing source reference: " + name)
        path = packet_path.parent / spec["path"]
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != spec["sha256"]:
            raise ValueError("changed or absent source: " + name)
        verified[name] = spec["sha256"]
    stop = packet.get("stopping_required")
    lanes = packet.get("marked_highway_lane_count")
    arrangement = packet.get("traffic_queue_arrangement")
    right = packet.get("right_side_feasibility")
    if stop is not True or type(lanes) is not int or lanes < 1:
        raise ValueError("supported crossing stop and total marked lane count required")
    if arrangement not in ("one_queue", "two_queues", "unresolved"):
        raise ValueError("reviewed traffic queue arrangement required")
    if right not in ("rightmost_feasible", "left_of_feasible", "unresolved"):
        raise ValueError("reviewed right-side feasibility required")
    return {"format": "c202480-crossing-branch-evidence-v1",
            "source_hashes": verified,
            "two_queue_evidence": arrangement,
            "marked_four_or_more_qualification": lanes >= 4,
            "two_queue_prohibition_context": arrangement == "two_queues" and lanes < 4,
            "right_side_evidence": right,
            "right_side_duty_remains_independent": True,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}

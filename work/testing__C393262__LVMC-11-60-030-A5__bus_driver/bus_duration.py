"""Source-bound interval measurement for a designated bus stop.

A duration is an observed quantity. This module never decides a legal verdict.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_bound(root: Path, ref: dict, expected_kind: str) -> dict:
    rel = ref.get("path")
    if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
        raise ValueError("unsafe source path")
    target = (root / rel).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError("missing source: " + str(rel))
    if sha(target) != ref.get("sha256"):
        raise ValueError("changed source: " + str(rel))
    value = json.loads(target.read_text())
    if value.get("kind") != expected_kind:
        raise ValueError("wrong source kind: " + expected_kind)
    return value


def measure(root: Path, refs: dict, *, expected_frames: int = 900, diagnostic: bool = False) -> dict:
    kinds = {
        "site": "reviewed_bus_stop_site",
        "designation": "bus_stop_duration_designation",
        "identity": "bus_operator_identity",
        "activity": "bus_activity_review",
        "native": "native_bus_frame_ledger",
    }
    packets = {key: read_bound(root, refs[key], kind) for key, kind in kinds.items()}
    if any(p.get("source_class") == "synthetic_diagnostic" for p in packets.values()) and not diagnostic:
        raise ValueError("synthetic diagnostic source cannot establish original measurement")
    site, designation, identity, activity, native = (packets[k] for k in kinds)
    if site.get("cell_id") != "C393262" or site.get("layout") != "residence_district" or site.get("stop_kind") != "bus_stop":
        raise ValueError("wrong site or stop kind")
    if not site.get("reviewer") or not site.get("designation_source_sha256") or not site.get("boundary_source_sha256"):
        raise ValueError("missing independently reviewed stop source")
    if designation.get("stop_id") != site.get("stop_id") or designation.get("authority") != "City Traffic Engineer":
        raise ValueError("designation does not bind this stop and authority")
    d = designation.get("applicable_duration_s")
    if not isinstance(d, (int, float)) or d <= 0 or not designation.get("conditions_reviewed"):
        raise ValueError("missing actual applicable designated duration or conditions")
    if designation.get("source_sha256") != site.get("designation_source_sha256"):
        raise ValueError("site designation source mismatch")
    if identity.get("bus_id") != native.get("bus_id") or identity.get("tour_bus") is not False or not identity.get("covered_operator"):
        raise ValueError("covered non-tour bus/operator identity unproved")
    rows = native.get("frames")
    if not isinstance(rows, list) or len(rows) != expected_frames:
        raise ValueError("incomplete Native frame ledger")
    for i, row in enumerate(rows):
        if row.get("frame") != i or abs(row.get("time_s", -1) - i / 20) > 0.00001:
            raise ValueError("Native frame/time join failed")
        if row.get("bus_id") != identity["bus_id"]:
            raise ValueError("bus identity changed in frame ledger")
        if not isinstance(row.get("inside_stop_boundary"), bool):
            raise ValueError("missing body-to-stop boundary observation")
    events = activity.get("events")
    if not isinstance(events, list) or len(events) < 2 or not activity.get("independent_reviewer"):
        raise ValueError("missing independently reviewed activity transitions")
    conduct = activity.get("conduct")
    if conduct not in ("stand", "park"):
        raise ValueError("standing/parking conduct unresolved")
    start, end = events[0], events[-1]
    if start.get("event") != "start" or end.get("event") != "end":
        raise ValueError("complete activity start/end not observed")
    begin = start.get("frame"); finish = end.get("frame")
    if not isinstance(begin, int) or not isinstance(finish, int) or begin < 0 or finish >= expected_frames or finish <= begin:
        raise ValueError("activity interval outside capture")
    if any(not rows[i]["inside_stop_boundary"] for i in range(begin, finish + 1)):
        raise ValueError("bus body left designated stop during measured interval")
    if any(e.get("event") in ("load", "unload", "merchandise") for e in events):
        raise ValueError("activity changed; independent interval segmentation required")
    observed = (finish - begin) / 20
    return {
        "case_measurement": "bus_stop_standing_or_parking_duration",
        "site_stop_id": site["stop_id"],
        "conduct": conduct,
        "observed_duration_s": observed,
        "applicable_designated_duration_s": float(d),
        "difference_s": observed - float(d),
        "interval_frames": [begin, finish],
        "source_refs": refs,
        "diagnostic_only": bool(diagnostic),
        "legal_verdict": None,
    }

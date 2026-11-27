"""Independent saved-original structural audit for parked-departure capture.

This checks source binding and completeness. Actual visibility and statutory
judgment still require review of real Native output and legal source context.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from parked_activity import measure_original_activity
from parked_construction import ASSIGNMENT, VARIANTS
from native_acquisition import CAMERAS, FRAME_COUNT


def _json(path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("original source missing: " + path.name)
    return json.loads(path.read_text())


def audit(path, case_id, *, require_native_attestation=False):
    """Return source-bound structural findings from one immutable attempt."""
    if not case_id.startswith(ASSIGNMENT + "__") or case_id.removeprefix(ASSIGNMENT + "__") not in VARIANTS:
        raise ValueError("wrong exact parked-departure case")
    root = Path(path)
    inventory = _json(root / "inventory.json")
    diagnostic = inventory.get("source_kind") == "synthetic_fixture"
    if inventory.get("diagnostic_fixture") is True and require_native_attestation:
        raise ValueError("diagnostic fixture cannot attest physical Native capture")
    count = 9 if diagnostic else FRAME_COUNT
    expected = inventory.get("source_sha256")
    if not isinstance(expected, dict) or set(expected) != {
            "site.json", "plan.json", "actors.json", "activity-seal.json",
            "frame-map.json", "activity-measurement.json"}:
        raise ValueError("saved original source inventory incomplete")
    for name, digest in expected.items():
        target = root / name
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError("saved original source hash differs: " + name)
    plan = _json(root / "plan.json")
    actors = _json(root / "actors.json")
    site = _json(root / "site.json")
    frame_map = _json(root / "frame-map.json")
    if (inventory.get("case_id") != case_id or plan.get("case_id") != case_id or
            site.get("case_id") != case_id or frame_map.get("case_id") != case_id):
        raise ValueError("saved original case identity differs")
    if (inventory.get("source_kind") != ("synthetic_fixture" if diagnostic else "original_native") or
            inventory.get("frame_count") != count or inventory.get("rate_hz") != 20):
        raise ValueError("saved original inventory incomplete")
    if require_native_attestation and inventory.get("diagnostic_fixture") is not False:
        raise ValueError("diagnostic fixture cannot attest physical Native capture")
    if not isinstance(frame_map.get("frames"), list) or len(frame_map["frames"]) != count:
        raise ValueError("saved original frame map incomplete")
    for index, row in enumerate(frame_map["frames"]):
        if row.get("frame") != index or abs(row.get("time_s", -1) - index / 20) > 1e-5:
            raise ValueError("saved original frame map discontinuity")
        if index and (row.get("native_frame") != frame_map["frames"][index - 1]["native_frame"] + 1 or
                      abs(row.get("native_time_s", -1) - frame_map["frames"][index - 1]["native_time_s"] - 0.05) > 0.001):
            raise ValueError("saved Native frame map discontinuity")
    for label, key in (("ego", "ego_vehicle_id"), ("other", "other_vehicle_id"),
                       ("driver", "driver_actor_id")):
        if not actors.get(key):
            raise ValueError("saved original " + label + " actor absent")
    if inventory.get("map_sha256") != site.get("reviewed_sources", {}).get("map", {}).get("sha256"):
        raise ValueError("saved map source binding differs")
    if hashlib.sha256((root / "road.xodr").read_bytes()).hexdigest() != inventory["map_sha256"]:
        raise ValueError("saved Native map hash differs")
    if diagnostic and inventory.get("media") != {}:
        raise ValueError("diagnostic camera inventory must be generated separately")
    if not diagnostic and (not isinstance(inventory.get("media"), dict) or set(inventory["media"]) != CAMERAS):
        raise ValueError("saved original four-camera inventory incomplete")
    for name in (() if diagnostic else CAMERAS):
        media = inventory["media"][name]
        filename = name + ".zip"
        if media.get("path") != filename:
            raise ValueError("original camera path differs")
        target = root / filename
        if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest() != media.get("sha256"):
            raise ValueError("original camera source hash differs: " + name)
        with zipfile.ZipFile(target) as archive:
            names = archive.namelist()
            if len(names) != count or len(set(names)) != count:
                raise ValueError("original camera frames incomplete: " + name)
            for index, entry in enumerate(names):
                native_frame = frame_map["frames"][index]["native_frame"]
                if entry != f"{index:04d}-{native_frame}.png" or not archive.read(entry).startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera frame invalid: " + name)
    activity = root / "activity.jsonl"
    if hashlib.sha256(activity.read_bytes()).hexdigest() != inventory.get("activity_sha256"):
        raise ValueError("saved original activity source hash differs")
    measured = measure_original_activity(activity, root / "activity-seal.json", case_id,
                                         diagnostic=diagnostic)
    if measured != _json(root / "activity-measurement.json"):
        raise ValueError("saved original activity measurement differs")
    return {"case_id": case_id, "structural_status": "passed",
            "frame_count": count, "camera_count": 0 if diagnostic else len(CAMERAS),
            "diagnostic_fixture": inventory["diagnostic_fixture"],
            "physical_completion": False, "legal_conclusion": "unreviewed",
            "activity_sha256": inventory["activity_sha256"]}

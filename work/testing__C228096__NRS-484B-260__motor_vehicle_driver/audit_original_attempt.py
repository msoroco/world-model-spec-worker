"""Independent original-source inventory and frame/actor audit."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile

from private_way_construction import ASSIGNMENT, CASES
from private_way_site import REQUIRED_SOURCES

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError("original source missing: " + path.name)
    return json.loads(path.read_text())


def audit(root, case_id, *, require_native_attestation=False):
    root = Path(root)
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if case_id != ASSIGNMENT + "__" + variant or variant not in CASES:
        raise ValueError("wrong exact private-way case")
    inventory = read(root / "inventory.json")
    diagnostic = inventory.get("source_kind") == "synthetic_fixture"
    if require_native_attestation and diagnostic:
        raise ValueError("diagnostic fixture cannot attest original Native capture")
    count = 9 if diagnostic else 900
    if inventory.get("case_id") != case_id or inventory.get("frame_count") != count:
        raise ValueError("original inventory case or frame count differs")
    site = read(root / "site.json")
    actors = read(root / "actors.json")
    frame_map = read(root / "frame-map.json")
    seal = read(root / "motion-seal.json")
    motion_path = root / "motion.jsonl"
    if motion_path.is_symlink() or not motion_path.is_file():
        raise ValueError("original source missing: motion.jsonl")
    if (site.get("case_id") != case_id or frame_map.get("case_id") != case_id or
            seal.get("case_id") != case_id or
            inventory.get("motion_sha256") != sha(motion_path) or
            inventory.get("frame_map_sha256") != sha(root / "frame-map.json") or
            seal.get("motion_sha256") != sha(motion_path) or
            seal.get("site_sha256") != sha(root / "site.json")):
        raise ValueError("original private-way source hash or identity differs")
    if not all(site.get("reviewed_assertions", {}).get(name) is True for name in
               ("private_ownership", "restricted_public_access", "destination_public_highway",
                "permitted_vehicular_use", "feasible_connection")):
        raise ValueError("original private/highway context incomplete")
    for name in REQUIRED_SOURCES:
        item = site.get("sources", {}).get(name, {})
        source = root / item.get("path", "missing")
        if source.is_symlink() or not source.is_file() or sha(source) != item.get("sha256"):
            raise ValueError("original reviewed site source differs: " + name)
    mapping = frame_map.get("frames", [])
    rows = [json.loads(line) for line in motion_path.read_text().splitlines() if line]
    if len(mapping) != count or len(rows) != count:
        raise ValueError("original private-way frame history incomplete")
    expected_sides = set(CASES[variant][1])
    expected_actors = actors.get("highway_vehicles", {})
    if set(expected_actors) != expected_sides or not actors.get("ego_vehicle_id"):
        raise ValueError("original highway actor inventory incomplete")
    first_native = mapping[0]["native_frame"]
    first_time = mapping[0]["native_time_s"]
    highway_frames = []
    progress = {side: [] for side in expected_sides}
    for index, (frame, row) in enumerate(zip(mapping, rows)):
        if (frame.get("frame") != index or frame.get("native_frame") != first_native + index or
                abs(frame.get("native_time_s", -1) - first_time - index / 20) > .005 or
                row.get("frame") != index or row.get("native_frame") != frame["native_frame"] or
                abs(row.get("time_s", -1) - frame["native_time_s"]) > 1e-4):
            raise ValueError("original private-way frame/time join differs")
        observed = row.get("highway_vehicles", [])
        if {a.get("side") for a in observed} != expected_sides:
            raise ValueError("all approaching highway vehicles not observed")
        for actor in observed:
            side = actor["side"]
            if actor.get("actor_id") != expected_actors[side] or not isinstance(actor.get("distance_to_connection_m"), (int, float)):
                raise ValueError("original highway actor identity/position differs")
            progress[side].append(actor["distance_to_connection_m"])
        if row.get("ego_on_highway") is True:
            highway_frames.append(index)
    if not highway_frames or any(not any(b < a for a, b in zip(values, values[1:])) for values in progress.values()):
        raise ValueError("original highway entry or actor approach absent")
    if not diagnostic:
        camera = inventory.get("camera_archives", {})
        if set(camera) != set(CAMERAS):
            raise ValueError("original four-camera inventory incomplete")
        for view in CAMERAS:
            item = camera[view]
            archive = root / item["path"]
            if archive.is_symlink() or sha(archive) != item["sha256"]:
                raise ValueError("original camera source hash differs: " + view)
            with zipfile.ZipFile(archive) as source:
                if len(source.namelist()) != count:
                    raise ValueError("original camera frame count differs")
    return {"case_id": case_id, "frame_count": count, "diagnostic_fixture": diagnostic,
            "motion_sha256": sha(motion_path), "inventory_sha256": sha(root / "inventory.json"),
            "highway_actor_ids": expected_actors, "first_highway_frame": min(highway_frames),
            "physical_acceptance": False, "legal_judgment": "unresolved"}

"""Measure original private-way approach motion without a legal verdict."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from private_way_construction import CASES, ASSIGNMENT


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_rows(path):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing required original source: " + path.name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError("original private-way motion history is empty")
    return rows


def measure(source: Path, case_id: str) -> dict:
    """Validate sealed 20 Hz history and report observed entry/approach facts."""
    source = Path(source)
    if not case_id.startswith(ASSIGNMENT + "__"):
        raise ValueError("wrong private-way assignment")
    variant = case_id.removeprefix(ASSIGNMENT + "__")
    if variant not in CASES:
        raise ValueError("unknown exact private-way case")
    history_file = source / "motion.jsonl"
    seal_file = source / "motion-seal.json"
    site_file = source / "site.json"
    for path in (history_file, seal_file, site_file):
        if not path.is_file() or path.is_symlink():
            raise ValueError("Missing required original source: " + path.name)
    seal = json.loads(seal_file.read_text())
    if seal.get("case_id") != case_id or seal.get("format") != "worker-private-way-motion-seal":
        raise ValueError("original motion seal identity differs")
    if seal.get("motion_sha256") != _sha(history_file) or \
            seal.get("site_sha256") != _sha(site_file):
        raise ValueError("original private-way source hash differs")
    rows = _read_rows(history_file)
    diagnostic = seal.get("diagnostic_fixture") is True
    count = 9 if diagnostic else 900
    if seal.get("frame_count") != count or len(rows) != count:
        raise ValueError("original private-way frame count incomplete")
    expected_sides = set(CASES[variant][1])
    actor_ids = {}
    ego_highway_frames = []
    ego_stop_frames = []
    approach_progress = {side: [] for side in expected_sides}
    first_native = rows[0].get("native_frame")
    first_time = rows[0].get("time_s")
    if type(first_native) is not int or type(first_time) not in (int, float):
        raise ValueError("original frame/time reference missing")
    for index, row in enumerate(rows):
        if row.get("case_id") != case_id or row.get("frame") != index:
            raise ValueError("original exact-case frame join differs")
        if row.get("native_frame") != first_native + index or \
                type(row.get("time_s")) not in (int, float) or \
                abs(row["time_s"] - first_time - index / 20) > .005:
            raise ValueError("original 20 Hz Native frame/time gap")
        if type(row.get("ego_on_highway")) is not bool or \
                type(row.get("ego_speed_mps")) not in (int, float) or \
                not math.isfinite(row["ego_speed_mps"]) or row["ego_speed_mps"] < 0:
            raise ValueError("original ego body or speed source missing")
        if row["ego_on_highway"]:
            ego_highway_frames.append(index)
        if row["ego_speed_mps"] < .1:
            ego_stop_frames.append(index)
        actors = row.get("highway_vehicles")
        if not isinstance(actors, list):
            raise ValueError("complete highway vehicle inventory missing")
        found_sides = set()
        seen_ids = set()
        for actor in actors:
            side = actor.get("side")
            identity = actor.get("actor_id")
            distance = actor.get("distance_to_connection_m")
            speed = actor.get("speed_mps")
            if side not in ("left", "right") or not isinstance(identity, str) or \
                    not identity or identity in seen_ids or \
                    type(distance) not in (int, float) or not math.isfinite(distance) or \
                    type(speed) not in (int, float) or not math.isfinite(speed) or speed < 0:
                raise ValueError("original highway actor measurement missing")
            if side not in expected_sides:
                raise ValueError("unplanned highway actor not represented in exact case")
            if side in found_sides:
                raise ValueError("more than one actor on an authored approach")
            seen_ids.add(identity)
            found_sides.add(side)
            actor_ids.setdefault(side, identity)
            if actor_ids[side] != identity:
                raise ValueError("highway actor identity changed across original frames")
            approach_progress[side].append(float(distance))
        if found_sides != expected_sides:
            raise ValueError("approaching highway actor missing from original frame")
    for side, values in approach_progress.items():
        if not any(values[index + 1] < values[index] and values[index] >= 0
                   for index in range(len(values) - 1)):
            raise ValueError("highway actor did not measurably approach: " + side)
    if not ego_highway_frames:
        raise ValueError("ego never reached the reviewed highway")
    return {
        "case_id": case_id,
        "frame_count": count,
        "diagnostic_fixture": diagnostic,
        "first_highway_frame": min(ego_highway_frames),
        "ego_highway_frames": ego_highway_frames,
        "ego_stop_frames": ego_stop_frames,
        "highway_actor_ids": actor_ids,
        "approach_first_last_distance_m": {
            side: [values[0], values[-1]] for side, values in approach_progress.items()},
        "source_hashes": {"motion.jsonl": _sha(history_file),
                          "motion-seal.json": _sha(seal_file),
                          "site.json": _sha(site_file)},
        "legal_yield_judgment": "unresolved",
        "physical_acceptance_claimed": False,
    }

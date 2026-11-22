"""Recompute corridor measurements from retained original pedestrian bodies."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from corridor_construction import measure_original
from corridor_map import verify_candidate_map


def _verified(root, entry):
    path = (root / entry["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("Missing required source: " + entry["path"])
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
        raise ValueError("Original source hash differs: " + entry["path"])
    return data


def measure_saved(root, manifest_path):
    root = Path(root)
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get("format") != "c143766-original-pedestrian-sources-v1":
        raise ValueError("unknown original source manifest")
    scene = json.loads(_verified(root, manifest["scene"]))
    map_entry = manifest["map"]
    _verified(root, map_entry)
    map_path = (root / map_entry["path"]).resolve()
    verified_map = verify_candidate_map(map_path)
    if scene["map_source_sha256"] != verified_map["map_sha256"]:
        raise ValueError("scene and original OpenDRIVE source differ")
    data = _verified(root, manifest["body_history"])
    try:
        frames = [json.loads(line) for line in data.decode().splitlines() if line]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Original body history is not valid JSONL") from exc
    if any(frame.get("case_id") != scene["case_id"] for frame in frames):
        raise ValueError("Original body history case identity differs")
    measured = measure_original(scene, frames)
    return {"case_id": scene["case_id"], "measurement": measured,
            "scene_sha256": manifest["scene"]["sha256"],
            "map_sha256": verified_map["map_sha256"],
            "body_history_sha256": manifest["body_history"]["sha256"],
            "original_source_verified": True,
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}

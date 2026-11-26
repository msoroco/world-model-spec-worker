"""Source-checked door actuation for the C228817 duration comparison.

Commands are intended motion. They are never evidence that the door moved.
The original camera frames and independently reviewed door state are required
by measure_door.py before a saved attempt may claim an open interval.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from controller import CASES, FPS, FRAMES, request


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _source(ref: dict, label: str) -> dict:
    _require(isinstance(ref, dict) and isinstance(ref.get("path"), str)
             and isinstance(ref.get("sha256"), str),
             f"Original {label} source reference required")
    path = Path(ref["path"])
    _require(path.is_file(), f"Original {label} source missing")
    raw = path.read_bytes()
    _require(hashlib.sha256(raw).hexdigest() == ref["sha256"],
             f"Original {label} source hash differs")
    return json.loads(raw)


def validate_review(review: dict, case: str) -> dict:
    """Reject an invented road side or transfer from an unbound proposal."""
    _require(case in CASES, "Unknown exact door comparison case")
    _require(review.get("source_kind") == "original_native_scene_review",
             "Original Native scene review required")
    sources = review.get("sources")
    _require(isinstance(sources, dict), "Original source inventory required")
    map_record = _source(sources.get("map"), "map")
    road_record = _source(sources.get("road"), "road")
    transfer_record = _source(sources.get("transfer"), "transfer")
    _require(map_record.get("map_name") == road_record.get("map_name")
             and isinstance(map_record.get("map_name"), str),
             "Original map and road source differ")
    _require(road_record.get("frozen_cell") ==
             {"layout": "road", "maneuver": "load_unload",
              "control": "other_vehicle"}, "Wrong frozen cell")
    _require(road_record.get("door_side") in ("left", "right")
             and road_record.get("passing_side") == road_record["door_side"],
             "Original traffic side or door side missing")
    _require(road_record.get("driver_actor_id")
             and road_record.get("driver_actor_id") == road_record.get("door_operator_actor_id")
             and road_record.get("passing_actor_id")
             and road_record["passing_actor_id"] != road_record["driver_actor_id"],
             "Original driver and passing actor identities required")
    _require(transfer_record.get("kind") in ("passenger", "cargo")
             and transfer_record.get("frame") == 200,
             "Original immediate transfer source at frame 200 required")
    if transfer_record["kind"] == "passenger":
        _require(transfer_record.get("pedestrian_actor_id")
                 and transfer_record.get("occupancy_delta") in (-1, 1),
                 "Original passenger and occupancy sources required")
    else:
        _require(transfer_record.get("cargo_actor_id"),
                 "Original identified cargo source required")
    offsets = road_record.get("passing_lateral_offsets_m")
    _require(isinstance(offsets, list) and len(offsets) == FRAMES
             and all(type(x) in (float, int) and math.isfinite(x) for x in offsets),
             "Complete original passing-actor path required")
    transit = list(range(110, 211))
    sign = 1 if road_record["passing_side"] == "left" else -1
    _require(all(sign * offsets[i] > 0.25 for i in transit),
             "Passing actor does not remain on reviewed traffic side")
    return {"case": case, "map_name": map_record["map_name"],
            "door_side": road_record["door_side"],
            "driver_actor_id": road_record["driver_actor_id"],
            "passing_actor_id": road_record["passing_actor_id"],
            "transfer_kind": transfer_record["kind"],
            "source_hashes": {key: sources[key]["sha256"] for key in
                              ("map", "road", "transfer")},
            "physical_completion": False, "legal_verdict": None}


def validate_setup(setup: dict, case: str) -> dict:
    """Validate source-bound intended scene without presuming it was observed."""
    _require(case in CASES, "Unknown exact door comparison case")
    _require(setup.get("source_kind") == "source_bound_native_setup",
             "Source-bound Native setup required")
    sources = setup.get("sources")
    _require(isinstance(sources, dict), "Native setup source inventory required")
    map_record = _source(sources.get("map"), "map")
    road_record = _source(sources.get("road"), "road")
    transfer_record = _source(sources.get("transfer"), "transfer")
    _require(map_record.get("map_name") == road_record.get("map_name")
             and isinstance(map_record.get("map_name"), str),
             "Source-bound map and road differ")
    _require(road_record.get("frozen_cell") ==
             {"layout": "road", "maneuver": "load_unload",
              "control": "other_vehicle"}, "Wrong frozen cell")
    _require(road_record.get("door_side") in ("left", "right")
             and road_record.get("passing_side") == road_record["door_side"],
             "Source-bound traffic-side door plan missing")
    _require(transfer_record.get("kind") in ("passenger", "cargo")
             and transfer_record.get("frame") == 200,
             "Source-bound immediate transfer plan missing")
    native = setup.get("native_setup", {})
    _require(all(type(native.get(name)) is int and native[name] >= 0
                 for name in ("ego_spawn_index", "passing_spawn_index", "walker_spawn_index")),
             "Actor spawn indices required")
    _require(native.get("door") in ("FL", "FR", "RL", "RR")
             and (road_record["door_side"] == "left") == native["door"].endswith("L"),
             "Native door differs from traffic-side plan")
    return {"case": case, "map_name": map_record["map_name"],
            "door_side": road_record["door_side"],
            "transfer_kind_requested": transfer_record["kind"],
            "source_hashes": {key: sources[key]["sha256"] for key in
                              ("map", "road", "transfer")},
            "physical_completion": False, "legal_verdict": None}


def command(case: str, frame: int) -> dict:
    row = request(case, frame)
    return {"frame": frame, "time_s": frame / FPS,
            "door_command": row["traffic_side_door_request"],
            "ego_brake": row["ego_hold_brake"],
            "transfer_command": row["transfer_request"],
            "passing_command": row["passing_vehicle_request"],
            "observed_door_open": None,
            "observed_transfer_complete": None}


def apply_door_command(vehicle, door, case: str, frame: int) -> dict:
    """Call CARLA's door actuator only at transitions; return request telemetry."""
    current = command(case, frame)
    previous = command(case, frame - 1) if frame else None
    if previous is None or current["door_command"] != previous["door_command"]:
        if current["door_command"] == "open":
            vehicle.open_door(door)
        else:
            vehicle.close_door(door)
    return current

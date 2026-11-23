"""Source-gated Native actor construction for the three traffic-count probes.

This prepares actor counts only. A later original capture must measure the
actors, their roles and the full 45-second history before any range is met.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


KINDS = {"additional_animal_count": "animal", "additional_bicycle_count": "bicycle",
         "additional_pedestrian_count": "pedestrian"}


def validate_packet(path: Path, *, case_id: str, kind: str, expected_count: int) -> dict:
    if kind not in KINDS or type(expected_count) is not int or expected_count < 0:
        raise ValueError("invalid exact traffic-count probe")
    packet = json.loads(Path(path).read_bytes())
    if (packet.get("format") != "c179789-native-count-probe-v1" or
            packet.get("case_id") != case_id or packet.get("kind") != kind or
            packet.get("expected_count") != expected_count or
            not packet.get("reviewer") or not packet.get("source_citation") or
            not isinstance(packet.get("map_sha256"), str) or len(packet["map_sha256"]) != 64):
        raise ValueError("count probe identity or reviewed source missing")
    actors = packet.get("actors")
    if not isinstance(actors, list) or len(actors) != expected_count:
        raise ValueError("count probe actor inventory differs")
    ids = set()
    for actor in actors:
        if (not isinstance(actor, dict) or actor.get("role") != KINDS[kind] or
                not actor.get("blueprint_id") or not actor.get("source_citation") or
                not isinstance(actor.get("transform"), dict)):
            raise ValueError("count probe actor source or placement missing")
        if actor.get("id") in ids or not isinstance(actor.get("id"), str) or not actor["id"]:
            raise ValueError("count probe actor identity duplicated or missing")
        ids.add(actor["id"])
        if set(actor["transform"]) != {"x", "y", "z", "yaw"}:
            raise ValueError("count probe actor transform incomplete")
        for value in actor["transform"].values():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not (-1e6 < value < 1e6):
                raise ValueError("count probe actor transform invalid")
    return packet


def construct(world, path: Path, *, case_id: str, kind: str, expected_count: int,
              transform_factory) -> dict:
    """Spawn only declared roles; fail closed and destroy all partial spawns."""
    packet = validate_packet(path, case_id=case_id, kind=kind, expected_count=expected_count)
    map_sha = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
    if map_sha != packet["map_sha256"]:
        raise ValueError("count probe OpenDRIVE source differs")
    blueprints = world.get_blueprint_library()
    spawned = []
    try:
        for actor in packet["actors"]:
            blueprint = blueprints.find(actor["blueprint_id"])
            if blueprint is None:
                raise ValueError("reviewed count probe blueprint unavailable")
            native_actor = world.try_spawn_actor(blueprint, transform_factory(**actor["transform"]))
            if native_actor is None:
                raise ValueError("count probe actor spawn failed")
            spawned.append(native_actor)
        return {"case_id": case_id, "kind": kind, "expected_count": expected_count,
                "actors": spawned, "packet_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
                "opendrive_sha256": map_sha, "physical_acceptance_claimed": False}
    except Exception:
        for actor in reversed(spawned):
            actor.destroy()
        raise

"""Reviewed physical actor construction for railway exception probes.

Spawning a flagman or signal prop does not establish duty, visibility or state;
the independent original-frame exception reader supplies those observations.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from rail_construction import TARGETS


def validate_exception_actor_source(root, packet, road_sha256, case_key):
    if case_key not in TARGETS:
        raise ValueError("unknown selected railway case")
    setup = TARGETS[case_key][2]
    if setup == "none":
        return None
    ref = packet.get("reviewed_exception_actor_source")
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise ValueError("reviewed railway exception actor source missing")
    root = Path(root).resolve()
    relative = Path(ref["path"])
    source = (root / relative).resolve()
    if (relative.is_absolute() or ".." in relative.parts or
            not source.is_relative_to(root) or not source.is_file() or
            source.is_symlink() or
            hashlib.sha256(source.read_bytes()).hexdigest() != ref.get("sha256")):
        raise ValueError("reviewed railway exception actor source missing or changed")
    review = json.loads(source.read_text())
    if (review.get("source_kind") != "railway_exception_actor_site" or
            not review.get("reviewer") or not review.get("source_citation") or
            review.get("road_sha256") != road_sha256 or
            review.get("exception_setup") != setup or
            not review.get("blueprint_id")):
        raise ValueError("reviewed railway exception actor identity incomplete")
    transform = review.get("transform")
    if (not isinstance(transform, dict) or
            any(type(transform.get(key)) not in (int, float) or
                not math.isfinite(transform[key]) for key in ("x", "y", "z", "yaw"))):
        raise ValueError("reviewed railway exception actor transform invalid")
    return review


def spawn_exception_actor(world, transform_factory, root, packet,
                          road_sha256, case_key):
    review = validate_exception_actor_source(
        root, packet, road_sha256, case_key)
    if review is None:
        return None
    if not callable(transform_factory):
        raise ValueError("Native railway exception transform factory missing")
    blueprint = world.get_blueprint_library().find(review["blueprint_id"])
    actor = world.try_spawn_actor(blueprint, transform_factory(**review["transform"]))
    if actor is None:
        raise ValueError("reviewed railway exception actor spawn failed")
    if not getattr(actor, "is_alive", False):
        actor.destroy()
        raise ValueError("reviewed railway exception actor not alive")
    observed = actor.get_transform().location
    if math.dist((observed.x, observed.y, observed.z),
                 tuple(review["transform"][key] for key in ("x", "y", "z"))) > .5:
        actor.destroy()
        raise ValueError("reviewed railway exception actor position differs")
    return actor

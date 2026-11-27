"""Source-gated railway occluder construction for selected sight targets."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

TARGETS = {
    "obscured_14mph": (14, True, "none"),
    "obscured_15mph": (15, True, "none"),
    "obscured_16mph": (16, True, "none"),
    "clear_view_16mph": (16, False, "none"),
    "flagman_16mph": (16, True, "flagman_on_duty"),
    "signal_nonwarning_16mph": (16, True, "visible_nonwarning_signal"),
    "signal_warning_16mph": (16, True, "visible_warning_signal"),
}


def validate_occluder_source(root, packet, road_sha256, case_key):
    if case_key not in TARGETS:
        raise ValueError("unknown selected railway case")
    if not TARGETS[case_key][1]:
        return None
    ref = packet.get("reviewed_occluder_source")
    if not isinstance(ref, dict):
        raise ValueError("reviewed railway occluder source missing")
    relative = Path(ref.get("path", ""))
    root = Path(root).resolve()
    source = (root / relative).resolve()
    if (relative.is_absolute() or ".." in relative.parts or
            not source.is_relative_to(root) or not source.is_file() or
            source.is_symlink() or
            hashlib.sha256(source.read_bytes()).hexdigest() != ref.get("sha256")):
        raise ValueError("reviewed railway occluder source missing or changed")
    review = json.loads(source.read_text())
    if (review.get("source_kind") != "railway_occluder_site" or
            not review.get("reviewer") or not review.get("source_citation") or
            review.get("road_sha256") != road_sha256 or
            review.get("target_ray") not in ("crossing", "rail_minus_400ft",
                                              "rail_plus_400ft") or
            not review.get("blueprint_id")):
        raise ValueError("reviewed railway occluder claim incomplete")
    transform = review.get("transform")
    if (not isinstance(transform, dict) or
            any(type(transform.get(key)) not in (int, float) or
                not math.isfinite(transform[key]) for key in ("x", "y", "z", "yaw"))):
        raise ValueError("reviewed railway occluder transform invalid")
    return review


def spawn_occluder(world, transform_factory, root, packet, road_sha256, case_key):
    review = validate_occluder_source(root, packet, road_sha256, case_key)
    if review is None:
        return None
    if not callable(transform_factory):
        raise ValueError("Native railway occluder transform factory missing")
    blueprint = world.get_blueprint_library().find(review["blueprint_id"])
    transform = transform_factory(**review["transform"])
    actor = world.try_spawn_actor(blueprint, transform)
    if actor is None:
        raise ValueError("reviewed railway occluder spawn failed")
    if not getattr(actor, "is_alive", False):
        actor.destroy()
        raise ValueError("reviewed railway occluder not alive")
    observed = actor.get_transform()
    position = observed.location
    if math.dist((position.x, position.y, position.z),
                 tuple(review["transform"][key] for key in ("x", "y", "z"))) > .5:
        actor.destroy()
        raise ValueError("reviewed railway occluder spawn position differs")
    return actor

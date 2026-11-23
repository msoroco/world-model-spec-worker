"""Source-gated construction for LVMC 11.16.040 intersection sight probes.

Import is CARLA-free.  The operator must supply a map-reviewed site packet; a
missing device or a convenient blueprint never establishes a legal exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot
from typing import Any


FEET_100_M = 30.48
MPH_15_MPS = 15 * 0.44704


class ConstructionError(ValueError):
    pass


@dataclass(frozen=True)
class Case:
    case_id: str
    occluder: str | None
    target_mps: float
    through: bool = False
    controlled: bool = False


CASES = {
    "blocked_below": Case("blocked_below", "west_building", 14 * .44704),
    "blocked_at": Case("blocked_at", "west_building", MPH_15_MPS),
    "blocked_above": Case("blocked_above", "west_building", 16 * .44704),
    "clear_at": Case("clear_at", None, MPH_15_MPS),
    "through_blocked": Case("through_blocked", "west_building", MPH_15_MPS, through=True),
    "controlled_blocked": Case("controlled_blocked", "west_building", MPH_15_MPS, controlled=True),
}


def _require_source(packet: dict[str, Any], key: str) -> Any:
    value = packet.get(key)
    if value is None or not packet.get(f"{key}_source_sha256"):
        raise ConstructionError(f"{key} needs map or authority source and SHA256")
    return value


def validate_site(packet: dict[str, Any], case: Case) -> None:
    """Reject unsupported scene claims before acquiring any CARLA actor."""
    if _require_source(packet, "jurisdiction") != "Las Vegas municipal":
        raise ConstructionError("municipal jurisdiction unestablished")
    if _require_source(packet, "road_kind") not in ("street", "highway"):
        raise ConstructionError("junction is not an established street/highway intersection")
    arms = _require_source(packet, "entering_arms")
    if not isinstance(arms, list) or len(arms) < 3 or len(set(arms)) != len(arms):
        raise ConstructionError("all entering arms must be inventoried")
    if _require_source(packet, "ego_road_through") is not case.through:
        raise ConstructionError("through-street designation differs from case")
    if _require_source(packet, "traffic_controlled_intersection") is not case.controlled:
        raise ConstructionError("intersection control status differs from case")
    if not packet.get("boundary_source_sha256") or not packet.get("map_hash"):
        raise ConstructionError("intersection boundary and map identity required")
    route = packet.get("ego_route_xy")
    if not isinstance(route, list) or len(route) < 3:
        raise ConstructionError("ego route geometry missing")
    if not all(isinstance(p, list) and len(p) == 2 for p in route):
        raise ConstructionError("route point malformed")
    length = sum(hypot(b[0]-a[0], b[1]-a[1]) for a, b in zip(route, route[1:]))
    if length < FEET_100_M + 10:
        raise ConstructionError("route cannot cover last 100 feet and traversal")
    if case.occluder:
        occluders = packet.get("occluder_sites", {})
        obj = occluders.get(case.occluder)
        if not isinstance(obj, dict) or not obj.get("source_sha256"):
            raise ConstructionError("map-reviewed occluder transform missing")
        if not obj.get("blueprint_id") or not isinstance(obj.get("transform"), dict):
            raise ConstructionError("occluder blueprint or transform missing")
        if obj.get("affected_arm") not in arms:
            raise ConstructionError("occluder must target an inventoried entering arm")


def spawn_occluder(world: Any, packet: dict[str, Any], case: Case) -> Any | None:
    """Create the physical obstruction; caller owns actor cleanup in finally."""
    validate_site(packet, case)
    if not case.occluder:
        return None
    spec = packet["occluder_sites"][case.occluder]
    library = world.get_blueprint_library()
    blueprint = library.find(spec["blueprint_id"])
    actor = world.try_spawn_actor(blueprint, spec["transform"])
    if actor is None:
        raise ConstructionError("occluder spawn failed")
    if not getattr(actor, "is_alive", False):
        actor.destroy()
        raise ConstructionError("occluder not alive after spawn")
    return actor

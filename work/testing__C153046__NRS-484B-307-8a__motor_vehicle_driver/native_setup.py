"""Lazy Native actor creation from a reviewed one-way left-turn packet.

No CARLA import occurs here. Caller owns the world and supplies transform_factory.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from red_left_measurement import validate_site, _number, _xy, _dot, _cross


def _xyz(value, name):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("missing xyz " + name)
    return tuple(_number(x, name) for x in value)


def validate_spawn(packet_path):
    site = validate_site(packet_path)
    packet = json.loads(Path(packet_path).read_text())
    plan = packet.get("spawn_plan")
    if not isinstance(plan, dict) or set(plan) != {"ego", "pedestrians", "other_traffic"}:
        raise ValueError("reviewed spawn plan missing")
    ego = plan["ego"]
    if ego.get("lane_id") != site["left_lane_id"]:
        raise ValueError("ego not in extreme-left approach lane")
    xyz = _xyz(ego.get("location_xyz_m"), "ego")
    rotation = _xyz(ego.get("rotation_rpy_deg"), "ego rotation")
    if not ego.get("source_citation") or not ego.get("blueprint_id"):
        raise ValueError("uncited ego spawn")
    offset = tuple(xyz[i] - site["reference"][i] for i in (0, 1))
    if _dot(offset, site["direction"]) >= site["stop_progress_m"] - 2:
        raise ValueError("ego spawn not upstream of stop reference")
    heading = (math.cos(math.radians(rotation[2])), math.sin(math.radians(rotation[2])))
    if _dot(heading, site["direction"]) < 0.95:
        raise ValueError("ego heading differs from one-way approach")
    for kind in ("pedestrians", "other_traffic"):
        if not isinstance(plan[kind], list):
            raise ValueError("participant list missing")
        for actor in plan[kind]:
            _xyz(actor.get("location_xyz_m"), kind)
            _xyz(actor.get("rotation_rpy_deg"), kind)
            if not actor.get("blueprint_id") or not actor.get("source_citation") or not actor.get("route_source_citation"):
                raise ValueError("uncited participant spawn or route")
            if not isinstance(actor.get("route_points_xyz_m"), list) or len(actor["route_points_xyz_m"]) < 2:
                raise ValueError("participant route missing")
            for point in actor["route_points_xyz_m"]:
                _xyz(point, kind + " route")
    return site, plan


class NativeActors:
    def __init__(self, ego, signal, pedestrians, traffic, owned):
        self.ego, self.signal = ego, signal
        self.pedestrians, self.traffic, self.owned = pedestrians, traffic, owned

    def close(self):
        for actor in reversed(self.owned):
            actor.destroy()
        self.owned.clear()


def create(world, packet_path, transform_factory):
    site, plan = validate_spawn(packet_path)
    signals = [actor for actor in world.get_actors() if str(actor.id) == site["signal_actor_id"]]
    if len(signals) != 1:
        raise ValueError("official signal actor absent or ambiguous")
    owned = []
    try:
        library = world.get_blueprint_library()

        def spawn(spec):
            blueprint = library.find(spec["blueprint_id"])
            actor = world.try_spawn_actor(blueprint, transform_factory(_xyz(spec["location_xyz_m"], "spawn"),
                                                                _xyz(spec["rotation_rpy_deg"], "rotation")))
            if actor is None:
                raise ValueError("Native actor spawn failed")
            owned.append(actor)
            return actor

        ego = spawn(plan["ego"])
        pedestrians = [spawn(spec) for spec in plan["pedestrians"]]
        traffic = [spawn(spec) for spec in plan["other_traffic"]]
        return NativeActors(ego, signals[0], pedestrians, traffic, owned)
    except Exception:
        for actor in reversed(owned):
            actor.destroy()
        raise

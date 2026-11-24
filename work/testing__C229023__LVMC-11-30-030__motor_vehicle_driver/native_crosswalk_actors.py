"""Source-bound Native actors and original per-tick crosswalk observations.

This adapter owns spawned actors. Its route controller is an engineering proposal;
saved measurements, independent audits and physical review decide what occurred.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk_measurements import ASSIGNMENT_ID


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _source_plan(proposal: dict) -> dict:
    case_id = proposal.get("case_id")
    if proposal.get("assignment_id") != ASSIGNMENT_ID or not isinstance(case_id, str) or not case_id.startswith(ASSIGNMENT_ID + "__"):
        raise ValueError("exact source-bound crosswalk proposal required")
    entry = proposal.get("source")
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
        raise ValueError("original site packet source required")
    site_path = Path(entry["path"])
    if site_path.is_symlink() or not site_path.is_file() or hashlib.sha256(site_path.read_bytes()).hexdigest() != entry.get("sha256"):
        raise ValueError("original site packet changed")
    site = json.loads(site_path.read_bytes())
    actor_entry = site.get("sources", {}).get("actor_setup")
    if not isinstance(actor_entry, dict) or any(not isinstance(actor_entry.get(key), str) or not actor_entry[key]
                                                for key in ("path", "sha256", "citation")):
        raise ValueError("reviewed original actor setup source required")
    relative = Path(actor_entry["path"])
    if relative.is_absolute() or len(relative.parts) != 1:
        raise ValueError("actor setup must be a portable sibling source")
    source = site_path.parent / relative
    if source.is_symlink() or not source.is_file() or source.resolve().parent != site_path.parent.resolve():
        raise ValueError("regular original actor setup source required")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != actor_entry["sha256"]:
        raise ValueError("original actor setup source changed")
    plan = json.loads(raw)
    if plan.get("map_id") != proposal.get("map_id") or plan.get("case_id") != proposal.get("case_id"):
        raise ValueError("actor setup map or exact case differs")
    blueprints = plan.get("blueprints")
    heights = plan.get("spawn_z_m")
    if not isinstance(blueprints, dict) or set(blueprints) != {"ego", "lead", "pedestrian"}:
        raise ValueError("three original actor blueprints required")
    if any(not isinstance(value, str) or not value for value in blueprints.values()):
        raise ValueError("nonempty original actor blueprint ID required")
    if not (blueprints["ego"].startswith("vehicle.") and blueprints["lead"].startswith("vehicle.")
            and blueprints["pedestrian"].startswith("walker.pedestrian.")):
        raise ValueError("vehicle and pedestrian Native blueprint kinds required")
    if not isinstance(heights, dict) or set(heights) != set(blueprints) or not all(_finite(value) for value in heights.values()):
        raise ValueError("finite original actor spawn heights required")
    speed = plan.get("ego_target_speed_mps")
    pedestrian_speed = plan.get("pedestrian_speed_mps")
    if not _finite(speed) or not 0 < speed <= 15 or not _finite(pedestrian_speed) or not 0 < pedestrian_speed <= 3:
        raise ValueError("bounded engineering route speeds required")
    return plan


def _xy(location):
    return [float(location.x), float(location.y)]


class NativeCrosswalkActors:
    def __init__(self, *, world, carla, proposal: dict):
        self.world = world
        self.carla = carla
        self.proposal = proposal
        self.plan = _source_plan(proposal)
        cap = proposal.get("engineering_speed_cap_mps")
        if cap is not None:
            if not _finite(cap) or not 0 < cap <= self.plan["ego_target_speed_mps"]:
                raise ValueError("bounded fallback ego speed cap required")
            self.plan = dict(self.plan)
            self.plan["ego_target_speed_mps"] = cap
        self.actors = {}
        self.destroyed = False
        starts = {"ego": proposal["ego_route"][0], "lead": proposal["lead_stop_center"],
                  "pedestrian": proposal["pedestrian_route"][0]}
        destinations = {"ego": proposal["ego_route"][1], "lead": [starts["lead"][0] + 1, starts["lead"][1]],
                        "pedestrian": proposal["pedestrian_route"][1]}
        try:
            library = world.get_blueprint_library()
            for role in ("ego", "lead", "pedestrian"):
                start, destination = starts[role], destinations[role]
                if not (isinstance(start, list) and len(start) == 2 and all(_finite(x) for x in start)
                        and isinstance(destination, list) and len(destination) == 2 and all(_finite(x) for x in destination)):
                    raise ValueError("finite source route coordinates required")
                yaw = math.degrees(math.atan2(destination[1] - start[1], destination[0] - start[0]))
                blueprint = library.find(self.plan["blueprints"][role])
                if blueprint is None:
                    raise ValueError("original actor blueprint missing: " + role)
                transform = carla.Transform(carla.Location(x=start[0], y=start[1], z=self.plan["spawn_z_m"][role]),
                                            carla.Rotation(yaw=yaw))
                actor = world.try_spawn_actor(blueprint, transform)
                if actor is None:
                    raise RuntimeError("Native actor spawn failed: " + role)
                self.actors[role] = actor
            if len({str(actor.id) for actor in self.actors.values()}) != 3:
                raise ValueError("Native actor identities are not distinct")
        except BaseException:
            self.close()
            raise

    @property
    def actor_ids(self):
        return {role: str(actor.id) for role, actor in self.actors.items()}

    def control(self):
        """Apply an explicit route proposal before each synchronous world tick."""
        if self.destroyed:
            raise ValueError("Native actors already destroyed")
        ego = self.actors["ego"]
        position = ego.get_location()
        speed = ego.get_velocity()
        current_speed = math.sqrt(speed.x ** 2 + speed.y ** 2 + speed.z ** 2)
        if not _finite(current_speed):
            raise ValueError("nonfinite original ego speed")
        route = self.proposal["ego_route"]
        target = route[-1]
        if len(route) > 2 and position.x < route[1][0] - 1:
            target = route[1]
        dx, dy = target[0] - position.x, target[1] - position.y
        heading = math.degrees(math.atan2(dy, dx))
        yaw = ego.get_transform().rotation.yaw
        error = (heading - yaw + 180) % 360 - 180
        steer = max(-0.6, min(0.6, error / 45))
        if math.hypot(dx, dy) < 1.5 or self.proposal["ego_behavior"] == "wait" and position.x >= route[-1][0]:
            throttle, brake = 0.0, 1.0
        else:
            throttle = max(0.0, min(0.55, (self.plan["ego_target_speed_mps"] - current_speed) * 0.2))
            brake = 0.0 if current_speed <= self.plan["ego_target_speed_mps"] else 0.25
        ego.apply_control(self.carla.VehicleControl(throttle=throttle, steer=steer, brake=brake))
        self.actors["lead"].apply_control(self.carla.VehicleControl(throttle=0.0, brake=1.0))
        walker = self.actors["pedestrian"]
        walk_start, walk_end = self.proposal["pedestrian_route"]
        walk = walker.get_location()
        wx, wy = walk_end[0] - walk.x, walk_end[1] - walk.y
        distance = math.hypot(wx, wy)
        if distance < 0.3:
            direction, walk_speed = self.carla.Vector3D(x=0, y=0, z=0), 0.0
        else:
            direction = self.carla.Vector3D(x=wx / distance, y=wy / distance, z=0)
            walk_speed = self.plan["pedestrian_speed_mps"]
        walker.apply_control(self.carla.WalkerControl(direction=direction, speed=walk_speed))

    def observe(self, world_frame: int) -> dict:
        if self.destroyed or type(world_frame) is not int or world_frame < 0:
            raise ValueError("live original Native frame required")
        rows = {}
        for role, actor in self.actors.items():
            location = actor.get_location()
            row = {"actor_id": str(actor.id), "center": _xy(location),
                   "source_ref": f"native://world/frame/{world_frame}/actor/{actor.id}"}
            if role != "pedestrian":
                vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
                if len(vertices) != 8:
                    raise ValueError("eight original vehicle body vertices required")
                row["vertices"] = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
                velocity = actor.get_velocity()
                row["speed_mps"] = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
            rows[role] = row
        return rows

    def close(self):
        if self.destroyed:
            return
        self.destroyed = True
        for actor in reversed(list(self.actors.values())):
            actor.destroy()

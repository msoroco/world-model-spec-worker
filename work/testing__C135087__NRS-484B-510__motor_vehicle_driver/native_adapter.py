"""Source-bound CARLA placement bridge for the restricted-zone cases.

This bridge deliberately leaves motion, original pixels and graph collection to
an injected capture adapter. It provides the concrete Native construction used
by that adapter, and refuses to change the world before reviewing its binding.
"""

import copy
import math
from pathlib import Path

from site_geometry import load, point_at_station, station_of


class NativePlacement:
    def __init__(self, client, carla, plan, site_path):
        self.client, self.carla, self.plan = client, carla, plan
        self.site_path = Path(site_path)
        self.binding = load(site_path, plan)
        self.world = client.get_world()
        self.mapping = self.world.get_map()
        if self.mapping.name != self.binding["map_name"]:
            raise ValueError("live Native map differs from reviewed binding")
        for role, item in self.binding["fixed_actors"].items():
            actor = self.world.get_actors().find(item["actor_id"])
            if actor is None or actor.type_id != item["type_id"]:
                raise ValueError("live Native fixed actor differs: " + role)
        self.old_settings = copy.copy(self.world.get_settings())
        self.owned = []
        self.routes = {}
        self.schedule_entries = []
        self.sync_started = False

    def load_map(self, map_id):
        if map_id != self.plan.map_id or self.mapping.name != map_id:
            raise ValueError("Native map identity mismatch")
        settings = copy.copy(self.world.get_settings())
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        readback = self.world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-9:
            raise ValueError("Native 20 Hz world settings not confirmed")
        self.sync_started = True

    def mark_zone(self, start_m, end_m, purpose, source):
        if (start_m, end_m, purpose, source) != (
                self.plan.zone_start_m, self.plan.zone_end_m,
                self.plan.restricted_purpose, self.plan.restricted_source):
            raise ValueError("Native restricted-zone plan differs")
        for station in (start_m, end_m):
            point_at_station(self.binding, station)

    def _spawn(self, role, location, vehicle):
        if not self.sync_started:
            raise ValueError("Native world not synchronized")
        blueprint_id = self.binding["blueprints"][role]
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None:
            raise ValueError("reviewed Native blueprint unavailable: " + role)
        x, y, z = location
        place = self.carla.Location(x=x, y=y, z=z)
        if vehicle:
            waypoint = self.mapping.get_waypoint(place, project_to_road=False)
            if waypoint is None:
                raise ValueError("reviewed vehicle point has no live road waypoint")
            yaw = waypoint.transform.rotation.yaw
        else:
            yaw = float(self.binding.get("passenger_yaw_deg", 0))
        transform = self.carla.Transform(place, self.carla.Rotation(yaw=yaw))
        actor = self.world.try_spawn_actor(blueprint, transform)
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError("Native actor spawn/readback failed: " + role)
        self.owned.append(actor)
        if vehicle:
            actual = actor.get_transform().location
            observed = station_of(self.binding, (actual.x, actual.y, actual.z))
            target = self.plan.subject_stop_m if role == "subject" else self.plan.entrant_start_m
            if abs(observed - target) > self.binding["observation_tolerances_m"]["station"]:
                raise ValueError("Native vehicle spawn station readback differs")
        return actor

    def spawn_vehicle(self, role, station_m, vehicle_class):
        if role not in ("subject", "restricted-purpose-entrant"):
            raise ValueError("unknown vehicle role")
        key = "subject" if role == "subject" else "entrant"
        target = self.plan.subject_stop_m if key == "subject" else self.plan.entrant_start_m
        if station_m != target or not vehicle_class:
            raise ValueError("vehicle construction differs from reviewed plan")
        return self._spawn(key, point_at_station(self.binding, station_m), True)

    def spawn_pedestrian(self, role, station_m):
        if role != "passenger" or station_m != self.plan.subject_stop_m:
            raise ValueError("passenger construction differs from reviewed plan")
        return self._spawn("passenger", self.binding["passenger_spawn_m"], False)

    def set_route(self, actor, destination_m):
        if actor not in self.owned:
            raise ValueError("route actor not owned by this capture")
        if actor.type_id == self.binding["blueprints"]["passenger"]:
            self.routes[actor.id] = tuple(self.binding["passenger_door_m"])
        else:
            if destination_m != self.plan.entrant_destination_m:
                raise ValueError("entrant destination differs from reviewed plan")
            self.routes[actor.id] = point_at_station(self.binding, destination_m)

    def schedule(self, actor, action, at_s):
        if actor not in self.owned or not math.isfinite(float(at_s)) or at_s < 0:
            raise ValueError("Native schedule invalid")
        self.schedule_entries.append({"actor_id": actor.id, "action": action,
                                      "time_s": float(at_s)})

    def restore(self):
        failures = []
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except Exception as error:
                failures.append(str(error))
        self.owned.clear()
        if self.sync_started:
            try:
                self.world.apply_settings(self.old_settings)
                current = self.world.get_settings()
                if current.synchronous_mode != self.old_settings.synchronous_mode or \
                        current.fixed_delta_seconds != self.old_settings.fixed_delta_seconds:
                    failures.append("world settings restoration readback differs")
            except Exception as error:
                failures.append(str(error))
        if failures:
            raise ValueError("Native restoration failed: " + "; ".join(failures))
        return True

"""Lazy CARLA adapter for the C149555 signed yellow-curb freight construction.

This code is CPU importable. Its methods require a live world at execution time;
source gates precede all spawns. Physical curb paint, sign legibility, freight
transfer and camera visibility still need original-capture review.
"""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from xml.etree import ElementTree

from freight_contract import SourceError, read_sealed


class NativeCarlaAdapter:
    def __init__(self, world, site: dict, dossier: dict, carla_module=None):
        if carla_module is None:
            import carla as carla_module  # lazy import on the GPU host
        self.carla = carla_module
        self.world = world
        self.map = world.get_map()
        self.site = site
        self.dossier = dossier
        self.owned = []
        self.ego = None
        self.sign = None
        self.cargo = None
        self.carrier = None
        self.civil_window_selected = None

    def assert_native_map(self, expected_sha256: str) -> None:
        actual = hashlib.sha256(self.map.to_opendrive().encode("utf-8")).hexdigest()
        if actual != expected_sha256:
            raise SourceError("live OpenDRIVE map seal mismatch")
        if self.map.name != self.site.get("native_map_name"):
            raise SourceError("live Native map name mismatch")

    def assert_one_way_lane(self, road_id: int, lane_id: int) -> None:
        root = ElementTree.fromstring(self.map.to_opendrive())
        roads = [road for road in root.findall("road") if road.get("id") == str(road_id)]
        if len(roads) != 1:
            raise SourceError("reviewed Native road is absent")
        lanes = []
        for section in roads[0].findall("./lanes/laneSection"):
            for lane in section.findall("./left/lane") + section.findall("./right/lane"):
                if lane.get("type") == "driving":
                    lanes.append(int(lane.get("id")))
        if not lanes or lane_id not in lanes or {1 if lane > 0 else -1 for lane in lanes} != {1 if lane_id > 0 else -1}:
            raise SourceError("Native driving lanes do not verify one-way travel")
        waypoint = self.map.get_waypoint_xodr(road_id, lane_id, self.site["approach_station_m"])
        if waypoint is None or waypoint.road_id != road_id or waypoint.lane_id != lane_id:
            raise SourceError("Native approach waypoint is unavailable")

    def assert_yellow_curb(self, zone: dict, source_sha256: str) -> None:
        observation = read_sealed(self.site["curb_observation_path"], source_sha256)
        if observation.get("map_name") != self.map.name or observation.get("color") != "yellow":
            raise SourceError("reviewed curb observation is not yellow on this map")
        if observation.get("start_station_m") != zone.get("start_station_m") or observation.get("end_station_m") != zone.get("end_station_m"):
            raise SourceError("reviewed curb zone extent mismatch")
        if not observation.get("independent_pixel_review"):
            raise SourceError("yellow curb lacks reviewed original pixels")

    def set_civil_clock_window(self, conditions: dict, inside: bool) -> None:
        # CARLA simulation time is not a civil clock. The sourced civil context
        # must be selected and later joined to original frames by the finalizer.
        civil = self.site.get("civil_time_contexts", {}).get("inside" if inside else "outside")
        if not civil or not civil.get("source_sha256") or not civil.get("local_datetime") or not civil.get("timezone"):
            raise SourceError("missing sourced civil-time context")
        if not conditions.get("civil_windows"):
            raise SourceError("missing posted civil windows")
        self.civil_window_selected = civil

    def _blueprint(self, identifier: str):
        if not identifier:
            raise SourceError("reviewed blueprint ID missing")
        matches = self.world.get_blueprint_library().filter(identifier)
        exact = [item for item in matches if item.id == identifier]
        if len(exact) != 1:
            raise SourceError(f"reviewed CARLA blueprint unavailable: {identifier}")
        return exact[0]

    def _station_transform(self, station_m: float, lateral_m: float = 0.0):
        waypoint = self.map.get_waypoint_xodr(self.site["native_road_id"], self.site["native_lane_id"], station_m)
        if waypoint is None:
            raise SourceError("reviewed station has no Native waypoint")
        transform = waypoint.transform
        right = transform.get_right_vector()
        transform.location.x += lateral_m * right.x
        transform.location.y += lateral_m * right.y
        transform.location.z += self.site.get("spawn_height_m", 0.3)
        return transform

    def _spawn(self, identifier: str, transform, attach_to=None):
        actor = self.world.try_spawn_actor(self._blueprint(identifier), transform, attach_to=attach_to)
        if actor is None:
            raise SourceError(f"CARLA spawn failed: {identifier}")
        self.owned.append(actor)
        return actor

    def spawn_or_verify_sign(self, conditions: dict, source_sha256: str):
        observation = read_sealed(self.site["sign_observation_path"], source_sha256)
        if observation.get("verbatim_text") != conditions.get("verbatim_text") or observation.get("map_name") != self.map.name:
            raise SourceError("reviewed sign source does not match posted conditions")
        if not observation.get("independent_pixel_review"):
            raise SourceError("sign lacks reviewed original pixels")
        # A reviewed prop blueprint must carry the actual sign face. We never
        # substitute an annotation or JSON string for a physical sign.
        self.sign = self._spawn(self.site["sign_blueprint_id"], self._station_transform(self.site["sign_station_m"], self.site["sign_lateral_m"]))
        return self.sign.id

    def spawn_vehicle(self, vehicle_id: str, approach_station_m: float):
        if vehicle_id != self.dossier.get("vehicle_id"):
            raise SourceError("vehicle/dossier identity mismatch")
        self.ego = self._spawn(self.dossier["vehicle_blueprint_id"], self._station_transform(approach_station_m))
        return self.ego.id

    def _current_station(self):
        waypoint = self.map.get_waypoint(self.ego.get_location(), project_to_road=False)
        if waypoint is None or waypoint.road_id != self.site["native_road_id"] or waypoint.lane_id != self.site["native_lane_id"]:
            raise SourceError("ego left reviewed one-way lane")
        return waypoint.s

    def drive_to_station(self, ego_id, target_station_m: float):
        if self.ego is None or ego_id != self.ego.id:
            raise SourceError("wrong ego actor")
        if not math.isfinite(target_station_m):
            raise SourceError("nonfinite target station")
        target = self.map.get_waypoint_xodr(self.site["native_road_id"], self.site["native_lane_id"], target_station_m)
        if target is None:
            raise SourceError("target station lacks Native waypoint")
        # Closed-loop station control. No teleportation or inferred completion.
        max_ticks = int(self.site.get("approach_max_ticks", 500))
        for _ in range(max_ticks):
            station = self._current_station()
            distance = target_station_m - station
            if distance < -self.site.get("station_tolerance_m", 1.0):
                raise SourceError("ego overshot curb target")
            if abs(distance) <= self.site.get("station_tolerance_m", 1.0):
                return
            speed = self.ego.get_velocity().length()
            desired = min(self.site.get("approach_speed_mps", 4.0), max(0.8, distance * 0.4))
            throttle = 0.35 if speed < desired else 0.0
            brake = 0.35 if speed > desired + 0.5 else 0.0
            self.ego.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake))
            self.world.tick()
        raise SourceError("ego did not reach reviewed curb station")

    def stop_and_hold(self, ego_id):
        if self.ego is None or ego_id != self.ego.id:
            raise SourceError("wrong ego actor")
        for _ in range(int(self.site.get("brake_max_ticks", 80))):
            self.ego.apply_control(self.carla.VehicleControl(throttle=0.0, brake=1.0, hand_brake=True))
            self.world.tick()
            if self.ego.get_velocity().length() <= 0.1:
                return
        raise SourceError("ego did not stop at reviewed curb station")

    def spawn_freight(self, blueprint_id: str, zone: dict):
        station = (zone["start_station_m"] + zone["end_station_m"]) / 2
        self.cargo = self._spawn(blueprint_id, self._station_transform(station, self.site["cargo_lateral_m"]))
        return self.cargo.id

    def transfer_freight(self, ego_id, cargo_id, action: str):
        if self.ego is None or ego_id != self.ego.id or self.cargo is None or cargo_id != self.cargo.id:
            raise SourceError("cargo/ego identity mismatch")
        if action not in ("loading", "unloading"):
            raise SourceError("unsupported freight action")
        # A walker carries the authored cargo prop across the curb. This is
        # scripted prop motion, and the saved audit still requires original
        # pixels and actor trajectories before a transfer can be reported.
        station = self._current_station()
        self.carrier = self._spawn(self.site["carrier_blueprint_id"], self._station_transform(station, self.site["carrier_start_lateral_m"]))
        direction = 1.0 if action == "unloading" else -1.0
        right = self._station_transform(station).get_right_vector()
        walk_direction = self.carla.Vector3D(right.x * direction, right.y * direction, 0.0)
        for _ in range(int(self.site.get("transfer_ticks", 80))):
            self.carrier.apply_control(self.carla.WalkerControl(direction=walk_direction, speed=self.site.get("carrier_speed_mps", 0.8)))
            self.world.tick()
            cargo_transform = self.carrier.get_transform()
            cargo_transform.location.z += self.site["cargo_carry_height_m"]
            self.cargo.set_transform(cargo_transform)

    def cleanup(self):
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except RuntimeError:
                pass
        self.owned.clear()

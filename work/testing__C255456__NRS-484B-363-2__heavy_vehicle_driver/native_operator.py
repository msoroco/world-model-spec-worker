"""Lazy CARLA adapter for the source-reviewed heavy vehicle crossing-zone scene.

The reviewed site supplies Native spawns, map identity, beacon actor IDs and
camera mounts. This module owns actors and retains original post-tick readback.
Commanded speed and lamp state never stand in for actual motion or pixels.
"""

from __future__ import annotations

import math
from queue import Empty, Queue

from crossing_scene import _inside_polygon, require
from native_capture import SIZES, VIEWS


def _transform(carla, packet):
    require(isinstance(packet, dict) and set(packet) == {"x", "y", "z", "yaw"},
            "reviewed Native transform requires x/y/z/yaw")
    values = [float(packet[key]) for key in ("x", "y", "z", "yaw")]
    require(all(math.isfinite(value) for value in values), "nonfinite Native transform")
    return carla.Transform(carla.Location(x=values[0], y=values[1], z=values[2]),
                           carla.Rotation(yaw=values[3]))


def _bbox(actor):
    return [[point.x, point.y, point.z]
            for point in actor.bounding_box.get_world_vertices(actor.get_transform())]


class CrossingOperator:
    def __init__(self, world, site, case_id):
        self.world, self.site, self.case_id = world, site, case_id
        self.vehicle = None
        self.children = []
        self.cameras = {}
        self.queues = {}
        self.speed_mps = None
        self.light_actors = []
        self.sign_actor = None
        require(isinstance(site.get("native_vehicle_spawn"), dict),
                "reviewed heavy vehicle Native spawn missing")
        require(isinstance(site.get("native_camera_mounts"), dict) and
                set(site["native_camera_mounts"]) == set(VIEWS),
                "four reviewed Native camera mounts required")
        require(isinstance(site.get("native_child_spawns"), list) and
                len(site["native_child_spawns"]) == len(site["children_xy_m"]),
                "reviewed child Native spawns differ from child inventory")
        lamp_ids = site.get("native_beacon_lamp_actor_ids")
        require(isinstance(lamp_ids, list) and len(lamp_ids) == site["beacon_yellow_lamp_count"] and
                all(type(identifier) is int and identifier > 0 for identifier in lamp_ids),
                "reviewed individual beacon lamp actor IDs required")
        for identifier in lamp_ids:
            actor = world.get_actors().find(identifier)
            require(actor is not None and actor.is_alive and
                    callable(getattr(actor, "get_state", None)) and
                    callable(getattr(actor, "set_state", None)),
                    "reviewed controllable Native beacon actor absent")
            self.light_actors.append(actor)
        sign_id = site.get("native_sign_actor_id")
        require(type(sign_id) is int and sign_id > 0,
                "reviewed Native school-zone sign actor ID required")
        self.sign_actor = world.get_actors().find(sign_id)
        require(self.sign_actor is not None and self.sign_actor.is_alive,
                "reviewed Native sign actor absent")

    def build_school_crossing_zone(self, site, case):
        import carla
        require(site is self.site and case["case_id"] == self.case_id,
                "exact crossing-zone source/case mismatch")
        blueprint = self.world.get_blueprint_library().find(site["heavy_blueprint"])
        self.vehicle = self.world.try_spawn_actor(
            blueprint, _transform(carla, site["native_vehicle_spawn"]))
        require(self.vehicle is not None and self.vehicle.type_id == site["heavy_blueprint"],
                "heavy Native vehicle spawn/readback failed")
        if case["children_request"] == "children":
            child_blueprint_id = site.get("native_child_blueprint")
            require(isinstance(child_blueprint_id, str) and child_blueprint_id.startswith("walker."),
                    "reviewed Native child blueprint required")
            child_blueprint = self.world.get_blueprint_library().find(child_blueprint_id)
            for spawn in site["native_child_spawns"]:
                child = self.world.try_spawn_actor(child_blueprint, _transform(carla, spawn))
                require(child is not None and child.type_id == child_blueprint_id,
                        "reviewed Native child spawn/readback failed")
                self.children.append(child)
        self._spawn_cameras(carla)
        location = self.vehicle.get_location()
        inside = _inside_polygon([location.x, location.y], site["zone_polygon_xy_m"])
        require(inside == (case["zone_request"] == "inside"),
                "Native spawn differs from requested crossing-zone membership")
        return {"map_sha256": site["map_sha256"],
                "zone_polygon_xy_m": site["zone_polygon_xy_m"],
                "crosswalk_polygon_xy_m": site["crosswalk_polygon_xy_m"],
                "pupil_route_xy_m": site["pupil_route_xy_m"],
                "route_xy_m": site["route_xy_m"],
                "vehicle_blueprint": self.vehicle.type_id,
                "driver_id": site["driver_id"], "vehicle_id": self.vehicle.id,
                "children_xy_m": site["children_xy_m"] if self.children else [],
                "inside_designated_zone": inside,
                "school_in_session_today": site["school_in_session_today"],
                "time_window_label": site["time_window_label"],
                "beacon_or_sign_state": site["beacon_or_sign_state"],
                "beacon_yellow_lamp_count": len(self.light_actors),
                "beacon_alternating_capable": site["beacon_alternating_capable"]}

    def _spawn_cameras(self, carla):
        for view in VIEWS:
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            width, height = SIZES[view]
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(
                blueprint, _transform(carla, self.site["native_camera_mounts"][view]),
                attach_to=self.vehicle)
            require(sensor is not None, "Native camera spawn failed: " + view)
            queue = Queue(maxsize=8)
            sensor.listen(lambda image, q=queue: q.put(image))
            self.cameras[view] = sensor
            self.queues[view] = queue

    def configure_speed_controller(self, scene, speed_mps, case):
        require(scene["vehicle_id"] == self.vehicle.id and
                case["case_id"] == self.case_id and 0 < speed_mps < 30,
                "exact heavy speed controller mismatch")
        self.speed_mps = float(speed_mps)
        return {"vehicle_id": self.vehicle.id, "target_mps": self.speed_mps}

    def control_frame(self, case, index):
        import carla
        require(case["case_id"] == self.case_id and self.speed_mps is not None,
                "uninitialized exact heavy controller")
        velocity = self.vehicle.get_velocity()
        actual = math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)
        route = self.site["route_xy_m"]
        position = self.vehicle.get_location()
        target = route[-1]
        for point in route[1:]:
            if math.hypot(point[0]-position.x, point[1]-position.y) > 8:
                target = point
                break
        desired = math.atan2(target[1]-position.y, target[0]-position.x)
        yaw = math.radians(self.vehicle.get_transform().rotation.yaw)
        error = (desired-yaw+math.pi) % (2*math.pi)-math.pi
        self.vehicle.apply_control(carla.VehicleControl(
            throttle=max(0.0, min(.7, .18*(self.speed_mps-actual))),
            brake=max(0.0, min(.6, .22*(actual-self.speed_mps))),
            steer=max(-.7, min(.7, .9*error))))
        device = case["beacon_or_sign_request"]
        for lamp_index, lamp in enumerate(self.light_actors):
            active = (device == "operational_flashing" and
                      lamp_index == index % len(self.light_actors)) or (
                      device == "one_yellow_light" and lamp_index == 0 and index % 2 == 0) or (
                      device == "nonalternating_yellow" and lamp_index == 0)
            lamp.set_state(carla.TrafficLightState.Yellow if active else carla.TrafficLightState.Off)

    def _lamp_readback(self):
        import carla
        return [lamp.get_state() == carla.TrafficLightState.Yellow
                for lamp in self.light_actors]

    def read_original_context(self, site, case):
        require(site is self.site and case["case_id"] == self.case_id and self.vehicle is not None,
                "Native original context not constructed")
        context = {key: value for key, value in site.items() if not key.startswith("_")}
        context.update(case_id=self.case_id, vehicle_id=self.vehicle.id,
                       vehicle_blueprint=self.vehicle.type_id)
        for name, record in site["source_records"].items():
            context[name + "_source"] = record["path"]
            context[name + "_source_sha256"] = record["sha256"]
        context.update({key: site["timing_packet"][key] for key in (
            "local_datetime", "operation_end_local", "next_operation_start_local",
            "class_start_local", "class_end_local")})
        return context

    def read_original_frame(self, case, index, native_frame):
        require(case["case_id"] == self.case_id, "wrong original frame case")
        location = self.vehicle.get_location()
        velocity = self.vehicle.get_velocity()
        speed = math.sqrt(velocity.x**2+velocity.y**2+velocity.z**2)
        child_rows = [{"actor_id": child.id, "blueprint": child.type_id,
                       "position_m": [child.get_location().x, child.get_location().y,
                                      child.get_location().z],
                       "body_vertices_m": _bbox(child)} for child in self.children]
        yaw = math.radians(self.vehicle.get_transform().rotation.yaw)
        row = {"frame": index, "native_frame": native_frame, "time_s": index/20,
               "map_sha256": self.site["map_sha256"], "driver_id": self.site["driver_id"],
               "vehicle_id": self.vehicle.id, "vehicle_blueprint": self.vehicle.type_id,
               "heavy_speed_mps": speed,
               "inside_designated_zone": _inside_polygon(
                   [location.x, location.y], self.site["zone_polygon_xy_m"]),
               "beacon_yellow_lights_lit": self._lamp_readback(),
               "sign_limit_active": self.site["timing_packet"]["sign_limit_active"],
               "children_actor_ids": [str(child.id) for child in self.children],
               "children_actor_readback": child_rows,
               "actor_id": self.vehicle.id,
               "position_m": [location.x, location.y, location.z],
               "heading_xy": [math.cos(yaw), math.sin(yaw)],
               "body_vertices_m": _bbox(self.vehicle),
               "school_in_session_today": self.site["school_in_session_today"],
               "beacon_or_sign_state": case["beacon_or_sign_request"],
               "time_window_label": case["time_request"]}
        row.update({name + "_source_sha256": record["sha256"]
                    for name, record in self.site["source_records"].items()})
        return row

    def camera_rgb24(self, view, frame):
        import numpy as np
        require(view in self.queues, "unknown Native camera view")
        try:
            image = self.queues[view].get(timeout=15)
        except Empty as exc:
            raise ValueError("original synchronized camera frame missing: " + view) from exc
        require(image.frame == frame and (image.width, image.height) == SIZES[view],
                "original synchronized camera identity/dimensions differ: " + view)
        bgra = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(image.height, image.width, 4)
        return bgra[:, :, 2::-1].copy().tobytes()

    def owned_actors(self):
        return [self.vehicle, *self.children, *self.cameras.values()]

    def destroy(self, actor):
        if actor is None:
            return
        if callable(getattr(actor, "stop", None)):
            actor.stop()
        actor.destroy()


def make_adapter(world, site, case_id):
    return CrossingOperator(world, site, case_id)

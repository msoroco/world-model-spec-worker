"""Source-gated CARLA adapter for two-vehicle school-zone passing capture.

The site packet supplies surveyed Native spawns, routes, lamp actor IDs and
camera mounts. Command values are engineering controls; post-tick readback is
retained separately and physical/legal acceptance remains a local review.
"""
from __future__ import annotations

import math
from queue import Empty, Queue

from native_capture import SIZES, VIEWS
from school_pass import SOURCES


def need(value, message):
    if not value:
        raise ValueError(message)


def transform(carla, row):
    need(isinstance(row, dict) and set(row) == {"x", "y", "z", "yaw"},
         "reviewed Native transform incomplete")
    x, y, z, yaw = (float(row[k]) for k in ("x", "y", "z", "yaw"))
    need(all(math.isfinite(v) for v in (x, y, z, yaw)), "nonfinite Native transform")
    return carla.Transform(carla.Location(x=x, y=y, z=z), carla.Rotation(yaw=yaw))


def progress(point, route):
    """Nearest polyline station in metres, for post-tick physical order."""
    best = None
    station = 0.0
    for a, b in zip(route, route[1:]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = math.hypot(dx, dy)
        need(length > 0, "reviewed route contains zero segment")
        t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / (length * length)))
        foot = (a[0] + t * dx, a[1] + t * dy)
        distance = math.hypot(point[0] - foot[0], point[1] - foot[1])
        value = station + t * length
        if best is None or distance < best[0]:
            best = (distance, value)
        station += length
    need(best is not None, "reviewed route is empty")
    return best[1]


class SchoolPassOperator:
    def __init__(self, world, site, case_id):
        self.world, self.site, self.case_id = world, site, case_id
        self.actors = {}
        self.routes = {}
        self.camera_queues = {}
        self.sensors = []
        self.approach_gap_m = 12.0
        self.lane_change_lead_m = 18.0
        self.pass_start = None
        self.pass_end = None
        self.pass_requested = None
        self.beacon_request = None
        self.native_map = world.get_map().to_opendrive().encode()
        import hashlib
        need(hashlib.sha256(self.native_map).hexdigest() == site["map_sha256"],
             "loaded Native map differs from reviewed school-site geometry")
        for field in ("native_spawn_transforms", "native_vehicle_blueprints", "native_camera_mounts"):
            need(isinstance(site.get(field), dict), "reviewed CARLA site field missing: " + field)
        need(set(site["native_camera_mounts"]) == set(VIEWS), "four reviewed camera mounts missing")
        lamps = site.get("native_beacon_lamp_actor_ids")
        need(isinstance(lamps, list) and len(lamps) >= 2 and all(type(v) is int for v in lamps),
             "two original Native beacon lamp actors required")
        self.lamps = lamps
        self._read_lamps()

    def _read_lamps(self):
        for identifier in self.lamps:
            actor = self.world.get_actors().find(identifier)
            need(actor is not None and actor.is_alive, "reviewed Native beacon lamp actor missing")

    def configure_pass_controller(self, *, approach_gap_m, lane_change_lead_m):
        gap, lead = float(approach_gap_m), float(lane_change_lead_m)
        need(6 <= gap <= 30 and 8 <= lead <= 40,
             "fallback engineering controller outside reviewed range")
        self.approach_gap_m, self.lane_change_lead_m = gap, lead

    def spawn_vehicle(self, identity, xy, vehicle_class):
        import carla
        need(vehicle_class == "conventional_motor_vehicle" and identity in
             (self.site["ego_id"], self.site["target_id"]), "unexpected Native vehicle")
        spawn = self.site["native_spawn_transforms"].get(identity)
        identifier = self.site["native_vehicle_blueprints"].get(identity)
        need(spawn is not None and isinstance(identifier, str) and identifier.startswith("vehicle."),
             "reviewed Native vehicle spawn/blueprint missing")
        need(math.hypot(float(spawn["x"]) - xy[0], float(spawn["y"]) - xy[1]) <= 1.0,
             "Native spawn differs from surveyed route start")
        blueprint = self.world.get_blueprint_library().find(identifier)
        actor = self.world.try_spawn_actor(blueprint, transform(carla, spawn))
        need(actor is not None, "reviewed Native vehicle spawn failed")
        self.actors[identity] = actor
        if identity == self.site["ego_id"]:
            self._spawn_cameras(actor)
        return actor

    def _spawn_cameras(self, ego):
        import carla
        try:
            for view in VIEWS:
                blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
                width, height = SIZES[view]
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("sensor_tick", "0.05")
                sensor = self.world.spawn_actor(blueprint,
                                                transform(carla, self.site["native_camera_mounts"][view]),
                                                attach_to=ego)
                need(sensor is not None, "reviewed Native RGB sensor spawn failed: " + view)
                queue = Queue(maxsize=4)
                sensor.listen(lambda image, destination=queue: destination.put(image))
                self.sensors.append(sensor)
                self.camera_queues[view] = queue
        except Exception:
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()
            self.sensors.clear()
            raise

    def set_route(self, actor, points, lane_ids):
        need(actor in self.actors.values() and len(points) == len(lane_ids),
             "reviewed Native route actor/lanes differ")
        self.routes[actor.id] = list(points)

    def set_pass_window(self, ego, target, start, end, requested):
        need(ego is self.actors.get(self.site["ego_id"]) and
             target is self.actors.get(self.site["target_id"]), "pass actors differ")
        self.pass_start, self.pass_end, self.pass_requested = start, end, requested

    def set_beacon(self, operational, alternating_flash):
        self._read_lamps()
        self.beacon_request = {"operational": operational, "alternating_flash": alternating_flash}

    def read_beacon(self):
        self._read_lamps()
        packet = self.site["timing_packet"]
        from school_timing import derive
        facts = derive(packet)
        readback = {"operational": facts["beacon_operational"],
                    "alternating_flash": facts["alternating_flash_observed"]}
        need(readback == self.beacon_request, "reviewed beacon source and Native plan differ")
        return readback

    def _drive(self, actor, route, speed, lookahead_m=5.0):
        import carla
        location = actor.get_location()
        station = progress((location.x, location.y), route)
        target = route[-1]
        for point in route[1:]:
            if progress(point, route) >= station + lookahead_m:
                target = point
                break
        heading = math.atan2(target[1] - location.y, target[0] - location.x)
        yaw = math.radians(actor.get_transform().rotation.yaw)
        error = (heading - yaw + math.pi) % (2 * math.pi) - math.pi
        actual = actor.get_velocity().length()
        actor.apply_control(carla.VehicleControl(
            throttle=max(0.0, min(.65, .2 * (speed - actual))),
            brake=max(0.0, min(.5, .25 * (actual - speed))),
            steer=max(-.75, min(.75, .9 * error))))

    def control_frame(self, case_id, index):
        need(case_id == self.case_id and self.pass_start is not None,
             "uninitialized exact Native pass controller")
        ego, target = (self.actors[self.site[key]] for key in ("ego_id", "target_id"))
        self._drive(target, self.routes[target.id], 4.0)
        speed = 6.0 + .02 * (self.approach_gap_m - 12.0) if self.pass_requested else 3.5
        self._drive(ego, self.routes[ego.id], speed,
                    lookahead_m=self.lane_change_lead_m / 3)

    def read_original_context(self, site, case_id):
        need(case_id == self.case_id and self.beacon_request is not None,
             "Native school-pass context not constructed")
        self._read_lamps()
        context = {key: value for key, value in site.items() if not key.startswith("_")}
        context["native_ego_actor_id"] = self.actors[site["ego_id"]].id
        context["native_target_actor_id"] = self.actors[site["target_id"]].id
        context["native_beacon_lamp_actor_ids"] = self.lamps
        return context

    def read_original_frame(self, case_id, index, frame):
        need(case_id == self.case_id, "Native frame selected another case")
        ego, target = (self.actors[self.site[key]] for key in ("ego_id", "target_id"))
        a, b = ego.get_location(), target.get_location()
        ego_xy, target_xy = [a.x, a.y], [b.x, b.y]
        route = self.routes[ego.id]
        dx, dy = route[1][0] - route[0][0], route[1][1] - route[0][1]
        length = math.hypot(dx, dy)
        lateral = abs((ego_xy[0] - target_xy[0]) * dy - (ego_xy[1] - target_xy[1]) * dx) / length
        def vertices(actor):
            return [[v.x, v.y, v.z] for v in actor.bounding_box.get_world_vertices(actor.get_transform())]
        row = {"frame": index, "native_frame": frame, "original_frame": frame,
               "time_s": index / 20, "driver_id": self.site["driver_id"],
               "ego_id": self.site["ego_id"], "target_id": self.site["target_id"],
               "ego_xy": ego_xy, "target_xy": target_xy,
               "ego_route_progress_m": progress(ego_xy, route),
               "target_route_progress_m": progress(target_xy, route),
               "lateral_separation_m": lateral,
               "ego_actor_id": ego.id, "target_actor_id": target.id,
               "ego_body_vertices_m": vertices(ego), "target_body_vertices_m": vertices(target),
               "ego_vehicle_blueprint": ego.type_id, "target_vehicle_blueprint": target.type_id}
        row.update({key + "_source_sha256": self.site[key + "_source_sha256"] for key in SOURCES})
        return row

    def camera_rgb24(self, view, frame):
        import numpy as np
        need(view in self.camera_queues, "reviewed Native camera view missing")
        try:
            image = self.camera_queues[view].get(timeout=10)
        except Empty as error:
            raise ValueError("original RGB sensor callback absent: " + view) from error
        need(image.frame == frame and (image.width, image.height) == SIZES[view],
             "original RGB sensor frame/dimensions differ: " + view)
        bgra = np.frombuffer(image.raw_data, dtype=np.uint8).reshape(image.height, image.width, 4)
        return bgra[:, :, 2::-1].copy().tobytes()

    def map_bytes(self, world):
        need(world is self.world, "original Native map instance changed")
        return self.native_map

    def destroy(self, actor):
        if actor is self.actors.get(self.site["ego_id"]):
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()
            self.sensors.clear()
        actor.destroy()


def make_adapter(world, site, case_id):
    return SchoolPassOperator(world, site, case_id)

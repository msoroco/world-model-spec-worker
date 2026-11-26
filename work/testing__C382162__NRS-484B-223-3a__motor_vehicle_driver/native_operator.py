"""Lazy CARLA adapter for the reviewed center-turn-lane route.

The packet must name original Native road/lane IDs and camera poses. Controller
stations are engineering commands; observation uses post-tick Native readback.
"""
from __future__ import annotations

import math
from queue import Empty, Queue

from native_capture import CAMERA_DIMENSIONS, VIEWS


def _angle(value):
    return (value + math.pi) % (2 * math.pi) - math.pi


class Operator:
    def __init__(self):
        self.route_index = 0
        self.initial_yaw = None
        self.camera_queues = {}
        self.target_speed_mps = 5.0

    @staticmethod
    def _transform(carla, spec):
        if set(spec) != {"x", "y", "z", "yaw"}:
            raise ValueError("reviewed Native transform incomplete")
        values = [float(spec[name]) for name in ("x", "y", "z", "yaw")]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("reviewed Native transform nonfinite")
        return carla.Transform(carla.Location(x=values[0], y=values[1], z=values[2]),
                               carla.Rotation(yaw=values[3]))

    def site_readback(self, world, site):
        import carla

        road_map = world.get_map()
        for lane in site["lanes"]:
            native = lane.get("native_identity")
            if not isinstance(native, dict) or set(native) != {"road_id", "lane_id"}:
                raise ValueError("reviewed Native lane identity missing")
            points = lane["centreline_xy_m"]
            for point in (points[0], points[len(points) // 2], points[-1]):
                waypoint = road_map.get_waypoint(carla.Location(x=float(point[0]),
                                                               y=float(point[1]), z=0),
                                                 project_to_road=False,
                                                 lane_type=carla.LaneType.Driving)
                if waypoint is None or (waypoint.road_id, waypoint.lane_id) != (
                        native["road_id"], native["lane_id"]):
                    raise ValueError("reviewed center-lane topology differs from loaded Native map")
        return {name: site[name] for name in ("lanes", "junction", "route", "highway_road_id")}

    def spawn_vehicle(self, world, site, case_id):
        import carla

        identifier = site.get("ego_blueprint_id")
        if not isinstance(identifier, str) or not identifier.startswith("vehicle."):
            raise ValueError("reviewed motor-vehicle blueprint missing")
        blueprint = world.get_blueprint_library().find(identifier)
        vehicle = world.try_spawn_actor(blueprint, self._transform(carla, site["ego_spawn"]))
        if vehicle is None:
            raise ValueError("reviewed Native ego spawn failed")
        return vehicle

    def cameras(self, world, vehicle, views):
        import carla

        poses = world.get_map()  # Forces a live map readback before camera spawn.
        if poses is None or set(views) != set(VIEWS):
            raise ValueError("four original camera views required")
        site_poses = self.site["camera_poses"]
        if set(site_poses) != set(VIEWS):
            raise ValueError("reviewed four-camera pose plan missing")
        callbacks, sensors = {}, []
        try:
            for view in VIEWS:
                blueprint = world.get_blueprint_library().find("sensor.camera.rgb")
                width, height = CAMERA_DIMENSIONS[view]
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("sensor_tick", "0.05")
                sensor = world.spawn_actor(blueprint,
                                           self._transform(carla, site_poses[view]),
                                           attach_to=vehicle)
                if sensor is None:
                    raise ValueError("original RGB sensor spawn failed: " + view)
                queue = Queue(maxsize=4)
                sensor.listen(lambda image, destination=queue: destination.put(image))
                sensors.append(sensor)
                self.camera_queues[view] = queue

                def receive(frame, destination=queue, name=view):
                    try:
                        image = destination.get(timeout=5)
                    except Empty as exc:
                        raise ValueError("original camera callback absent: " + name) from exc
                    if image.frame != frame:
                        raise ValueError("original camera frame drift: " + name)
                    return image

                callbacks[view] = receive
            return callbacks, sensors
        except Exception:
            for sensor in reversed(sensors):
                try:
                    sensor.stop()
                finally:
                    sensor.destroy()
            raise

    def control(self, vehicle, site, case_id, index):
        import carla

        route = site["route"]["waypoints_xy_m"]
        position = vehicle.get_location()
        while self.route_index < len(route) - 1 and math.hypot(
                route[self.route_index][0] - position.x,
                route[self.route_index][1] - position.y) < 4:
            self.route_index += 1
        target = route[self.route_index]
        transform = vehicle.get_transform()
        desired_yaw = math.atan2(target[1] - position.y, target[0] - position.x)
        current_yaw = math.radians(transform.rotation.yaw)
        error = _angle(desired_yaw - current_yaw)
        speed = vehicle.get_velocity().length()
        target_speed = float(self.target_speed_mps)
        if not 1 <= target_speed <= 15:
            raise ValueError("reviewed engineering speed outside controller range")
        throttle = min(.5, max(0, .2 * (target_speed - speed)))
        brake = min(.6, max(0, .25 * (speed - target_speed)))
        vehicle.apply_control(carla.VehicleControl(throttle=throttle, brake=brake,
                                                   steer=max(-.8, min(.8, error * .8))))

    def observe(self, world, vehicle, site, frame):
        import carla

        waypoint = world.get_map().get_waypoint(vehicle.get_location(),
                                                project_to_road=False,
                                                lane_type=carla.LaneType.Driving)
        if waypoint is None:
            raise ValueError("original motor vehicle left Native road")
        native_id = (waypoint.road_id, waypoint.lane_id)
        lane = next((lane for lane in site["lanes"] if lane["native_identity"] ==
                     {"road_id": native_id[0], "lane_id": native_id[1]}), None)
        road_aliases = site.get("road_aliases", {})
        road_id = road_aliases.get(str(waypoint.road_id))
        if lane is not None:
            road_id = lane["road_id"]
        if not road_id:
            raise ValueError("original Native road not in reviewed route")
        if lane is None and not site["route"].get("side_lane_id"):
            raise ValueError("original Native lane not in reviewed route")
        lane_id = lane["id"] if lane is not None else site["route"]["side_lane_id"]
        yaw = math.radians(vehicle.get_transform().rotation.yaw)
        if self.initial_yaw is None:
            self.initial_yaw = yaw
        total = _angle(yaw - self.initial_yaw)
        maneuver = "left_turn" if total > .52 else "right_turn" if total < -.52 else "travel"
        return {"source_frame_id": frame, "actor_id": vehicle.id,
                "driver_id": site["driver_id"], "road_id": road_id,
                "lane_id": lane_id, "maneuver": maneuver}


def make_operator(world, site, case_id):
    operator = Operator()
    operator.site = site
    return operator

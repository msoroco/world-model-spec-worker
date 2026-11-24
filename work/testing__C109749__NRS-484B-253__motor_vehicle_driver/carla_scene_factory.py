"""Spawn and steer the reviewed C109749 left-turn scene in a live CARLA world.

This owns the six initial actors through WorldLease. Reciprocal cases require a
separate later opponent, so this two-vehicle factory rejects them explicitly.
Controls are engineering requests; original motion is measured after each tick.
"""
from __future__ import annotations

import math

from left_turn_measurements import body_occupancy
from native_acquisition import CAMERAS
from native_source_review import review


CAMERA_POSES = {
    "overview": ((-8.0, 0.0, 6.0), (-17.0, 0.0, 0.0)),
    "approach": ((-5.0, 0.0, 2.5), (-5.0, 0.0, 0.0)),
    "reference_corner": ((0.0, 3.0, 2.4), (-8.0, -45.0, 0.0)),
    "driver_reference": ((0.6, 0.0, 1.6), (0.0, 0.0, 0.0)),
}


def _transform(api, location, rotation):
    return api.Transform(api.Location(*location), api.Rotation(*rotation))


def _spawn_vehicle(world, api, lease, blueprint_id, point):
    bp = world.get_blueprint_library().find(blueprint_id)
    if not bp.id.startswith("vehicle."):
        raise ValueError("reviewed vehicle blueprint required")
    location = api.Location(x=float(point["x_m"]), y=float(point["y_m"]), z=0.0)
    waypoint = world.get_map().get_waypoint(location, project_to_road=False)
    if waypoint is None:
        raise ValueError("reviewed spawn waypoint absent")
    transform = waypoint.transform
    transform.location.z += 0.3
    actor = lease.own(world.try_spawn_actor(bp, transform))
    actor.set_autopilot(False)
    return actor


def _camera(world, api, lease, ego, name, width, height):
    bp = world.get_blueprint_library().find("sensor.camera.rgb")
    for key, value in (("image_size_x", width), ("image_size_y", height),
                       ("fov", 90), ("sensor_tick", 0.05)):
        bp.set_attribute(key, str(value))
    offset, rotation = CAMERA_POSES[name]
    sensor = world.try_spawn_actor(bp, _transform(api, offset, rotation), attach_to=ego)
    return lease.own(sensor)


class RouteControls:
    def __init__(self, api, request, packet):
        self.api = api
        self.request = request
        self.polygon = packet["intersection_polygon"]
        self.ego_route = [(float(p["x_m"]), float(p["y_m"])) for p in request["ego_route"]]
        self.other_route = [(float(p["x_m"]), float(p["y_m"])) for p in request["initial_opponent_route"]]
        self.ego_index = 1
        self.other_index = 1
        self.wait = request["controller"]["wait_for_initial_opponent"]
        self.target_speed = float(request["controller"]["target_speed_mps"])
        if not 0 < self.target_speed <= 20:
            raise ValueError("reviewed target speed outside controller envelope")
        self.ego_done = False
        self.other_done = False

    @staticmethod
    def _inside(actor, polygon):
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        if len(vertices) != 8:
            raise ValueError("original Native body vertices missing")
        points = [[float(v.x), float(v.y), float(v.z)] for v in vertices]
        return body_occupancy(points, polygon)["any_vertex_inside"]

    def _drive(self, actor, route, index, target_speed):
        transform = actor.get_transform()
        here = transform.location
        while index < len(route) - 1 and math.hypot(
                route[index][0] - here.x, route[index][1] - here.y) < 2.5:
            index += 1
        target = route[index]
        forward = transform.get_forward_vector()
        desired = math.atan2(target[1] - here.y, target[0] - here.x)
        heading = math.atan2(forward.y, forward.x)
        error = math.atan2(math.sin(desired - heading), math.cos(desired - heading))
        steer = max(-1.0, min(1.0, error / 0.6))
        speed = float(actor.get_velocity().length())
        if not math.isfinite(speed):
            raise ValueError("original Native speed invalid")
        end = index == len(route) - 1 and math.hypot(
            target[0] - here.x, target[1] - here.y) < 2.0
        demand = 0.0 if end else target_speed
        throttle = max(0.0, min(0.65, 0.25 * (demand - speed)))
        brake = max(0.0, min(1.0, 0.5 * (speed - demand)))
        if demand == 0:
            brake = max(brake, 0.7)
        actor.apply_control(self.api.VehicleControl(throttle=throttle, brake=brake,
                                                    steer=steer, hand_brake=False))
        return index, end

    def __call__(self, ego, opponent):
        opponent_in_junction = self._inside(opponent, self.polygon)
        ego_target = 0.0 if self.wait and opponent_in_junction else self.target_speed
        self.ego_index, self.ego_done = self._drive(
            ego, self.ego_route, self.ego_index, ego_target)
        self.other_index, self.other_done = self._drive(
            opponent, self.other_route, self.other_index, self.target_speed)


def make_scene_factory(api):
    """Return the exact scene factory consumed by live_capture.run."""
    def scene_factory(*, world, request, packet, lease):
        review(packet, carla_map=world.get_map(),
               location_factory=lambda x, y: api.Location(x=x, y=y))
        if request["controller"]["wait_for_later_opponent"] is not None:
            raise ValueError("reciprocal case requires a separately spawned later opponent")
        ego = _spawn_vehicle(world, api, lease, request["ego_blueprint_id"],
                             request["ego_spawn_waypoint"])
        opponent = _spawn_vehicle(world, api, lease, request["opponent_blueprint_id"],
                                  request["initial_opponent_spawn_waypoint"])
        if ego.id == opponent.id:
            raise ValueError("original Native vehicle identities alias")
        signal = int(api.VehicleLightState.LeftBlinker)
        if request["controller"]["signal_left"]:
            ego.set_light_state(api.VehicleLightState(signal))
        cameras = {}
        dimensions = [request["capture"]["overview_resolution"],
                      *request["capture"]["detail_resolutions"]]
        for name, size in zip(CAMERAS, dimensions):
            cameras[name] = _camera(world, api, lease, ego, name, *size)
        return {"ego": ego, "opponent": opponent, "cameras": cameras,
                "control_step": RouteControls(api, request, packet)}
    return scene_factory

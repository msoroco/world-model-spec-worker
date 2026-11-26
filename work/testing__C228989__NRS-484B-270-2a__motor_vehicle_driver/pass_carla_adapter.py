"""CARLA bridge for one reviewed NRS 484B.270(2)(a) original capture.

The reviewed packet supplies Native map/asset identities. Every observation
comes from the live world. Control gains are engineering knobs, not legal
thresholds. This module is imported only by the CARLA Python interpreter.
"""

from __future__ import annotations

from io import BytesIO
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue

from package_spec import CAMERA_NAMES, CAMERAS
from pass_controller import Observation


def need(value, message):
    if not value:
        raise ValueError(message)


def bounded(value, lower, upper, name):
    need(type(value) in (int, float) and math.isfinite(value) and lower <= value <= upper,
         "invalid physical controller " + name)
    return float(value)


def _heading_to(source, target):
    return math.degrees(math.atan2(target.y - source.y, target.x - source.x))


def _angle_delta(target, current):
    return (target - current + 180.0) % 360.0 - 180.0


class CarlaPassAdapter:
    native_attested = True

    def __init__(self, host, port, case_id, *, carla_module=None):
        if carla_module is None:
            import carla as carla_module
        self.carla = carla_module
        self.client = carla_module.Client(str(host), int(port))
        self.client.set_timeout(20.0)
        self.world = self.client.get_world()
        self.map = self.world.get_map()
        packet_path = os.environ.get("C228989_REVIEWED_PACKET")
        need(packet_path, "reviewed Native packet environment missing")
        self.packet = json.loads(Path(packet_path).read_text())
        need(self.packet.get("case_id") == case_id, "reviewed packet selects another case")
        self.original_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        self.owned_sensors = []
        self.camera_queues = {}
        self.last_frame = None
        self.last_time_s = None
        self.ego_actor = None

    def map_name(self):
        return self.map.name

    def _waypoint(self, location):
        waypoint = self.map.get_waypoint(location, project_to_road=True,
                                         lane_type=self.carla.LaneType.Driving)
        need(waypoint is not None, "Native driving waypoint missing")
        return waypoint

    def lane_at(self, xy):
        location = self.carla.Location(x=float(xy[0]), y=float(xy[1]), z=0.0)
        waypoint = self._waypoint(location)
        return waypoint.road_id, waypoint.lane_id

    def _lane_id(self, actor):
        waypoint = self._waypoint(actor.get_location())
        matches = [lane["lane_id"] for lane in self.packet["lanes"]
                   if (lane["native_road_id"], lane["native_lane_id"]) ==
                   (waypoint.road_id, waypoint.lane_id)]
        need(len(matches) == 1, "live actor left reviewed lane inventory")
        return matches[0]

    def spawn(self, blueprint_id, xy, yaw_deg):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        waypoint = self._waypoint(self.carla.Location(x=float(xy[0]), y=float(xy[1]), z=0.0))
        transform = self.carla.Transform(
            self.carla.Location(x=float(xy[0]), y=float(xy[1]),
                                z=waypoint.transform.location.z + .4),
            self.carla.Rotation(yaw=float(yaw_deg)))
        actor = self.world.try_spawn_actor(blueprint, transform)
        need(actor is not None, "reviewed Native actor could not spawn")
        if self.ego_actor is None:
            self.ego_actor = actor
        return actor

    def actor_blueprint(self, actor):
        return actor.type_id

    def actor_lane(self, actor):
        waypoint = self._waypoint(actor.get_location())
        return waypoint.road_id, waypoint.lane_id

    def destroy(self, actor):
        if actor.is_alive:
            actor.destroy()

    def _camera_pose(self, name, actors):
        ego = actors["ego"].get_location()
        control = actors["control"].get_location()
        axis = self.packet["road_forward"]
        left = (-axis[1], axis[0])
        middle = self.carla.Location(x=(ego.x + control.x) / 2,
                                     y=(ego.y + control.y) / 2, z=1.0)
        if name == "overview":
            offset = (-15.0, 25.0, 28.0)
        elif name == "approach":
            offset = (-22.0, -7.0, 5.0)
        elif name == "reference_corner":
            offset = (20.0, 9.0, 6.0)
        else:
            offset = (-4.0, 1.0, 2.0)
        position = self.carla.Location(x=middle.x + offset[0] * axis[0] + offset[1] * left[0],
                                       y=middle.y + offset[0] * axis[1] + offset[1] * left[1],
                                       z=middle.z + offset[2])
        target = middle if name != "driver_reference" else control
        planar = math.hypot(target.x - position.x, target.y - position.y)
        pitch = math.degrees(math.atan2(target.z - position.z, planar))
        return self.carla.Transform(position, self.carla.Rotation(
            pitch=pitch, yaw=_heading_to(position, target)))

    def _start_cameras(self, actors):
        if self.owned_sensors:
            return
        library = self.world.get_blueprint_library()
        for profile in CAMERAS:
            name = profile["name"]
            blueprint = library.find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(profile["width"]))
            blueprint.set_attribute("image_size_y", str(profile["height"]))
            blueprint.set_attribute("fov", str(profile["fov_deg"]))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(blueprint, self._camera_pose(name, actors))
            self.owned_sensors.append(sensor)
            stream = Queue()
            sensor.listen(lambda image, stream=stream: stream.put(image))
            self.camera_queues[name] = stream

    def read_context(self, actors):
        self._start_cameras(actors)
        packet = self.packet
        axis = packet["road_forward"]
        lanes = []
        for lane in packet["lanes"]:
            forward = axis if lane["travel_direction"] == "forward" else [-axis[0], -axis[1]]
            lanes.append({"lane_id": lane["lane_id"], "forward": forward,
                          "source_ref": lane["source_ref"],
                          "immediate_left_lane_id": lane.get("immediate_left_lane_id")})
        return {"case_id": packet["case_id"],
                "map_sha256": next(ref["sha256"] for ref in packet["source_refs"] if ref.get("role") == "map"),
                "ego_kind": "motor_vehicle", "control_kind": packet["control_kind"],
                "ego_driver_source": packet["ego_driver_source"],
                "control_rider_source": packet["control_rider_source"],
                "road_origin": packet["spawn_xy"]["ego"], "road_forward": axis,
                "lanes": lanes, "ego_initial_lane_id": self._lane_id(actors["ego"]),
                "control_initial_lane_id": self._lane_id(actors["control"]),
                "immediate_left_lane_id": packet["immediate_left_lane_id"],
                "lane_restrictions_source": packet["lane_restrictions_source"],
                "left_lane_traffic_source": packet["surrounding_traffic_source"],
                "left_lane_obstructions_source": packet["lane_obstructions_source"],
                "surrounding_trajectories_source": packet["surrounding_traffic_source"]}

    def observe_pass(self, actors):
        packet = self.packet
        ego = actors["ego"]
        control = actors["control"]
        axis = packet["road_forward"]
        e = ego.get_location()
        c = control.get_location()
        gap = (c.x - e.x) * axis[0] + (c.y - e.y) * axis[1]
        ev = ego.get_velocity()
        cv = control.get_velocity()
        relative = (ev.x - cv.x) * axis[0] + (ev.y - cv.y) * axis[1]
        ego_waypoint = self._waypoint(e)
        left_lane = packet["immediate_left_lane_id"]
        occupants = []
        if left_lane is not None:
            for actor in self.world.get_actors().filter("vehicle.*"):
                if actor.id in {ego.id, control.id}:
                    continue
                position = actor.get_location()
                if math.hypot(position.x - e.x, position.y - e.y) > 60:
                    continue
                try:
                    if self._lane_id(actor) == left_lane:
                        occupants.append(str(actor.id))
                except ValueError:
                    continue
        lane_change = ego_waypoint.lane_change
        left_allowed = bool(lane_change & self.carla.LaneChange.Left)
        return Observation(ego_lane=self._lane_id(ego), control_lane=self._lane_id(control),
                           immediate_left_lane=left_lane,
                           same_direction_lane_count=sum(lane["travel_direction"] == "forward"
                                                     for lane in packet["lanes"]),
                           longitudinal_gap_m=gap, relative_speed_mps=relative,
                           left_lane_occupants=tuple(sorted(occupants)),
                           left_lane_restricted=(left_lane is not None and
                                                 self._lane_id(ego) != left_lane and
                                                 not left_allowed),
                           left_lane_obstructed=False,
                           source_frame=max(0, self.world.get_snapshot().frame))

    def apply_pass_control(self, actor, intent, profile):
        profile = profile or {}
        target_speed = bounded(profile.get("target_speed_mps", 10.0), 1.0, 20.0,
                               "target_speed_mps")
        lookahead = bounded(profile.get("lookahead_m", 4.0), 2.0, 20.0,
                            "lookahead_m")
        gain = bounded(profile.get("lane_entry_gain", 1.0), .1, 2.0,
                       "lane_entry_gain")
        if intent["longitudinal"] == "hold_back":
            target_speed = min(target_speed, 3.0)
        elif intent["longitudinal"] == "follow_control":
            target_speed = min(target_speed, 6.0)
        waypoint = self._waypoint(actor.get_location())
        if intent["lane_change"] == "immediate_left":
            left = waypoint.get_left_lane()
            need(left is not None and (left.road_id, left.lane_id) ==
                 self._native_lane(self.packet["immediate_left_lane_id"]),
                 "sampled Native left lane differs from reviewed packet")
            waypoint = left
        ahead = waypoint.next(lookahead)
        need(ahead, "Native steering lookahead absent")
        target = ahead[0].transform.location
        heading = actor.get_transform().rotation.yaw
        error = _angle_delta(_heading_to(actor.get_location(), target), heading)
        steer = max(-.8, min(.8, error / 45.0 * gain))
        velocity = actor.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        throttle = max(0.0, min(.65, (target_speed - speed) * .2))
        brake = max(0.0, min(.8, (speed - target_speed) * .25))
        actor.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake,
                                                      steer=steer))

    def _native_lane(self, lane_id):
        lane = next(row for row in self.packet["lanes"] if row["lane_id"] == lane_id)
        return lane["native_road_id"], lane["native_lane_id"]

    def tick(self, actors):
        for name, sensor in zip(CAMERA_NAMES, self.owned_sensors):
            sensor.set_transform(self._camera_pose(name, actors))
        for role in ("control", "occupant"):
            actor = actors.get(role)
            if actor is not None:
                actor.apply_control(self.carla.VehicleControl(throttle=.22, steer=0.0))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native world tick/snapshot mismatch")
        self.last_frame = frame
        self.last_time_s = snapshot.timestamp.elapsed_seconds
        return {"frame": frame, "time_s": self.last_time_s}

    def _vertices(self, actor):
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        need(len(vertices) == 8, "Native actor body requires eight vertices")
        return [[point.x, point.y, point.z] for point in vertices]

    def read_pass_row(self, frame, actors):
        need(frame == self.last_frame, "actor row differs from Native snapshot")
        ego, control = actors["ego"], actors["control"]
        occupied = list(self.observe_pass(actors).left_lane_occupants)
        def speed(actor):
            value = actor.get_velocity()
            return math.sqrt(value.x ** 2 + value.y ** 2 + value.z ** 2)
        return {"origin": "native_world_snapshot", "frame": frame,
                "time_s": self.last_time_s,
                "ego_vertices": self._vertices(ego),
                "control_vertices": self._vertices(control),
                "ego_lane_id": self._lane_id(ego),
                "control_lane_id": self._lane_id(control),
                "left_lane_occupied_actor_ids": occupied,
                "ego_speed_mps": speed(ego), "control_speed_mps": speed(control)}

    def read_cameras(self, frame, actors):
        need(frame == self.last_frame and set(self.camera_queues) == set(CAMERA_NAMES),
             "Native camera synchronization missing")
        from PIL import Image
        cameras = {}
        for name in CAMERA_NAMES:
            stream = self.camera_queues[name]
            image = None
            for _ in range(8):
                try:
                    candidate = stream.get(timeout=10)
                except Empty as error:
                    raise ValueError("Native camera frame missing: " + name) from error
                if candidate.frame == frame:
                    image = candidate
                    break
                if candidate.frame > frame:
                    raise ValueError("Native camera frame advanced past actor frame")
            need(image is not None, "Native camera did not join frame")
            rgb = Image.frombytes("RGBA", (image.width, image.height),
                                  bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            output = BytesIO()
            rgb.save(output, format="PNG")
            cameras[name] = {"frame": frame, "time_s": self.last_time_s,
                             "png": output.getvalue()}
        return cameras

    def brake(self):
        if self.ego_actor is not None and self.ego_actor.is_alive:
            self.ego_actor.apply_control(self.carla.VehicleControl(brake=1.0))

    def restore(self):
        for sensor in reversed(self.owned_sensors):
            if sensor.is_alive:
                sensor.stop()
                sensor.destroy()
        self.owned_sensors.clear()
        self.world.apply_settings(self.original_settings)


def create_adapter(host, port, case_id):
    return CarlaPassAdapter(host, port, case_id)

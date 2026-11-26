"""Live CARLA bridge for a reviewed one-lane bicycle or scooter pass.

The reviewed packet fixes Native map, actor, lane and control sources. This
module is loaded by the local CARLA Python interpreter during owned capture.
Engineering steering gains do not decide legal safety or due care.
"""

from io import BytesIO
import json
import math
import os
from pathlib import Path
from queue import Empty, Queue

from passing_controller import Sample


CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def need(value, message):
    if not value:
        raise ValueError(message)


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def angle_delta(target, current):
    return (target - current + 180.0) % 360.0 - 180.0


class CarlaPassingAdapter:
    native_attested = True

    def __init__(self, host, port, case_id, *, carla_module=None):
        if carla_module is None:
            import carla as carla_module
        self.carla = carla_module
        self.client = carla_module.Client(str(host), int(port))
        self.client.set_timeout(20.0)
        self.world = self.client.get_world()
        self.map = self.world.get_map()
        packet_path = os.environ.get("C272352_REVIEWED_PACKET")
        need(packet_path, "reviewed Native packet environment missing")
        self.packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
        need(self.packet.get("case_id") == case_id,
             "reviewed Native packet selects another case")
        self.original_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        self.actors = []
        self.sensors = []
        self.camera_queues = {}
        self.last_frame = None
        self.last_time_s = None

    def map_name(self):
        return self.map.name

    def waypoint(self, location):
        waypoint = self.map.get_waypoint(location, project_to_road=True,
                                         lane_type=self.carla.LaneType.Driving)
        need(waypoint is not None, "Native driving waypoint missing")
        return waypoint

    def lane_at(self, xy):
        location = self.carla.Location(x=float(xy[0]), y=float(xy[1]), z=0.0)
        waypoint = self.waypoint(location)
        return waypoint.road_id, waypoint.lane_id

    def spawn(self, blueprint_id, xy, yaw_deg):
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        location = self.carla.Location(x=float(xy[0]), y=float(xy[1]), z=0.0)
        waypoint = self.waypoint(location)
        transform = self.carla.Transform(
            self.carla.Location(x=location.x, y=location.y,
                                z=waypoint.transform.location.z + .4),
            self.carla.Rotation(yaw=float(yaw_deg)))
        actor = self.world.try_spawn_actor(blueprint, transform)
        need(actor is not None, "reviewed Native participant failed to spawn")
        self.actors.append(actor)
        return actor

    def actor_blueprint(self, actor):
        return actor.type_id

    def actor_lane(self, actor):
        waypoint = self.waypoint(actor.get_location())
        return waypoint.road_id, waypoint.lane_id

    def actor_id(self, actor):
        return actor.id

    def destroy(self, actor):
        if actor.is_alive:
            actor.destroy()

    def _axis(self, location):
        origin = self.packet["spawn_xy"]["ego"]
        forward = self.packet["road_forward"]
        dx, dy = location.x - origin[0], location.y - origin[1]
        return dx * forward[0] + dy * forward[1], -dx * forward[1] + dy * forward[0]

    def _world_xy(self, longitudinal, lateral, z):
        origin = self.packet["spawn_xy"]["ego"]
        forward = self.packet["road_forward"]
        return self.carla.Location(x=origin[0] + longitudinal * forward[0] -
                                   lateral * forward[1],
                                   y=origin[1] + longitudinal * forward[1] +
                                   lateral * forward[0], z=z)

    def _box(self, actor):
        vertices = actor.bounding_box.get_world_vertices(actor.get_transform())
        need(len(vertices) == 8, "original actor body requires eight vertices")
        positions = [self._axis(vertex) for vertex in vertices]
        xs = [item[0] for item in positions]
        ys = [item[1] for item in positions]
        return [min(xs), max(xs), min(ys), max(ys)]

    def _camera_pose(self, name, scene):
        ego = scene["ego"].get_location()
        rider = scene["control"].get_location()
        middle = self.carla.Location(x=(ego.x + rider.x) / 2,
                                     y=(ego.y + rider.y) / 2, z=1.0)
        forward = self.packet["road_forward"]
        left = (-forward[1], forward[0])
        offsets = {"overview": (-15.0, 25.0, 28.0),
                   "approach": (-22.0, -7.0, 5.0),
                   "reference_corner": (20.0, 9.0, 6.0),
                   "driver_reference": (-4.0, 1.0, 2.0)}
        along, aside, up = offsets[name]
        position = self.carla.Location(x=middle.x + along * forward[0] + aside * left[0],
                                       y=middle.y + along * forward[1] + aside * left[1],
                                       z=middle.z + up)
        target = rider if name == "driver_reference" else middle
        dx, dy, dz = target.x - position.x, target.y - position.y, target.z - position.z
        return self.carla.Transform(position, self.carla.Rotation(
            yaw=math.degrees(math.atan2(dy, dx)),
            pitch=math.degrees(math.atan2(dz, math.hypot(dx, dy)))))

    def _start_cameras(self, scene):
        if self.sensors:
            return
        profiles = {item["name"]: item for item in scene["survey"].get("cameras", [])}
        for index, name in enumerate(CAMERAS):
            profile = profiles.get(name, {})
            width = profile.get("width", 1920 if index == 0 else 1280)
            height = profile.get("height", 1080 if index == 0 else 720)
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(width))
            blueprint.set_attribute("image_size_y", str(height))
            blueprint.set_attribute("fov", str(profile.get("fov_deg", 75)))
            blueprint.set_attribute("sensor_tick", "0.05")
            sensor = self.world.spawn_actor(blueprint, self._camera_pose(name, scene))
            self.sensors.append(sensor)
            stream = Queue()
            sensor.listen(lambda image, stream=stream: stream.put(image))
            self.camera_queues[name] = stream

    def _opposing_path_clear(self, scene):
        ego = scene["ego"]
        e = ego.get_location()
        reverse = {(lane["native_road_id"], lane["native_lane_id"])
                   for lane in self.packet["lanes"] if lane["direction"] == "reverse"}
        for actor in self.world.get_actors().filter("vehicle.*"):
            if actor.id in {scene["ego"].id, scene["control"].id}:
                continue
            position = actor.get_location()
            if math.hypot(position.x - e.x, position.y - e.y) > 80:
                continue
            waypoint = self.waypoint(position)
            if (waypoint.road_id, waypoint.lane_id) in reverse:
                return False
        return True

    def observe_pass(self, scene):
        self._start_cameras(scene)
        ego_box = self._box(scene["ego"])
        rider_box = self._box(scene["control"])
        return Sample(original_frame=self.world.get_snapshot().frame,
                      ego_rear_m=ego_box[0], ego_front_m=ego_box[1],
                      bicycle_rear_m=rider_box[0], bicycle_front_m=rider_box[1],
                      ego_lateral_m=ego_box[2], bicycle_left_m=rider_box[3],
                      target_clearance_m=self.packet["target_clearance_m"],
                      opposing_path_clear=self._opposing_path_clear(scene),
                      centerline_source=self.packet["centerline_source"],
                      zone_source=self.packet["zone_source"],
                      traffic_source=self.packet["opposing_traffic_source"],
                      body_source="original Native bounding boxes")

    def apply_pass_control(self, ego, intent):
        need(len(self.actors) >= 2 and ego == self.actors[0],
             "original ego/control identity missing")
        rider_box = self._box(self.actors[1])
        ego_box = self._box(ego)
        half_width = (ego_box[3] - ego_box[2]) / 2
        current_x, current_y = self._axis(ego.get_location())
        target_y = rider_box[3] + intent["target_clearance_m"] + half_width + \
            float(intent.get("lateral_setpoint_margin_m", 0))
        if intent["mode"] in ("return_right", "return_right_early_requested"):
            target_y = float(self.packet["right_side_y"]) - half_width
        elif intent["mode"] == "hold_back":
            target_y = current_y
        if intent["route_request"] == "within_right_half" and \
                target_y + half_width > self.packet["centerline_y"]:
            intent = dict(intent, mode="hold_back")
            target_y = current_y
        target_speed = 8.0 * float(intent.get("approach_speed_scale", 1.0))
        if intent["mode"] == "hold_back":
            target_speed = 0.0
        lookahead = self._world_xy(current_x + 5.0, target_y,
                                   ego.get_location().z)
        location = ego.get_location()
        desired = math.degrees(math.atan2(lookahead.y - location.y,
                                          lookahead.x - location.x))
        heading_error = angle_delta(desired, ego.get_transform().rotation.yaw)
        steer = clamp(heading_error / 45.0, -.8, .8)
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        throttle = clamp((target_speed - speed) * .2, 0.0, .65)
        brake = clamp((speed - target_speed) * .25, 0.0, .8)
        ego.apply_control(self.carla.VehicleControl(throttle=throttle,
                                                    brake=brake, steer=steer))

    def tick(self, scene):
        for name, sensor in zip(CAMERAS, self.sensors):
            sensor.set_transform(self._camera_pose(name, scene))
        rider = scene["control"]
        if rider.type_id.startswith("vehicle."):
            rider.apply_control(self.carla.VehicleControl(throttle=.18, steer=0.0))
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native tick/snapshot identity mismatch")
        self.last_frame = frame
        self.last_time_s = snapshot.timestamp.elapsed_seconds
        return {"frame": frame, "time_s": self.last_time_s}

    def read_pass_row(self, scene, frame):
        need(frame == self.last_frame, "actor row differs from Native snapshot")
        ego_box = self._box(scene["ego"])
        rider_box = self._box(scene["control"])
        def speed(actor):
            value = actor.get_velocity()
            return math.sqrt(value.x ** 2 + value.y ** 2 + value.z ** 2)
        source = "original Native frame " + str(frame)
        return {"origin": "native_world_snapshot", "frame": frame,
                "time_s": self.last_time_s, "vehicle_box": ego_box,
                "bicycle_box": rider_box, "vehicle_speed_mps": speed(scene["ego"]),
                "bicycle_speed_mps": speed(scene["control"]),
                "vehicle_source": source + " ego bounding box",
                "bicycle_source": source + " rider bounding box",
                "lane_source": self.packet["centerline_source"],
                "opposing_traffic_source": self.packet["opposing_traffic_source"],
                "ego_lane": self.actor_lane(scene["ego"]),
                "rider_lane": self.actor_lane(scene["control"])}

    def read_cameras(self, scene, frame):
        need(frame == self.last_frame and set(self.camera_queues) == set(CAMERAS),
             "Native camera synchronization missing")
        from PIL import Image
        cameras = {}
        for name in CAMERAS:
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
            need(image is not None, "Native camera did not join actor frame")
            rgb = Image.frombytes("RGBA", (image.width, image.height),
                                  bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            output = BytesIO()
            rgb.save(output, format="PNG")
            cameras[name] = {"frame": frame, "time_s": self.last_time_s,
                             "png": output.getvalue()}
        return cameras

    def brake(self):
        if self.actors and self.actors[0].is_alive:
            self.actors[0].apply_control(self.carla.VehicleControl(brake=1.0))

    def restore(self):
        for sensor in reversed(self.sensors):
            if sensor.is_alive:
                sensor.stop()
                sensor.destroy()
        self.sensors.clear()
        self.world.apply_settings(self.original_settings)


def create_adapter(host, port, case_id):
    return CarlaPassingAdapter(host, port, case_id)

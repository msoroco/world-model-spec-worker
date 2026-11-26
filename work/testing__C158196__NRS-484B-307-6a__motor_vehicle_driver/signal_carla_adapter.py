"""Lazy CARLA bridge for source-reviewed NRS 484B.307(6)(a) capture.

The local scene packet must identify an OpenDRIVE map, a surveyed entry
polygon, the route waypoints, and official Native traffic-light actor IDs.
Live world readback supplies every observed indication and body position.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
import math
from pathlib import Path
from queue import Empty, Queue

from construction import CAMERAS


def need(value, message):
    if not value:
        raise ValueError(message)


def inside_polygon(x, y, polygon):
    need(len(polygon) >= 3, "surveyed intersection polygon missing")
    inside = False
    j = len(polygon) - 1
    for i, point in enumerate(polygon):
        prior = polygon[j]
        if (point[1] > y) != (prior[1] > y):
            crossing = (prior[0] - point[0]) * (y - point[1]) / (prior[1] - point[1]) + point[0]
            if x < crossing:
                inside = not inside
        j = i
    return inside


def signed_distance(x, y, polygon):
    minimum = float("inf")
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = dx * dx + dy * dy
        need(length > 0, "degenerate surveyed intersection polygon")
        t = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / length))
        minimum = min(minimum, math.hypot(x - (a[0] + t * dx), y - (a[1] + t * dy)))
    return minimum if inside_polygon(x, y, polygon) else -minimum


def heading_to(source, target):
    return math.degrees(math.atan2(target.y - source.y, target.x - source.x))


class CarlaSignalAdapter:
    native_attested = True

    def __init__(self, host, port, scene, *, carla_module=None):
        if carla_module is None:
            import carla as carla_module
        self.carla = carla_module
        self.client = carla_module.Client(str(host), int(port))
        self.client.set_timeout(20.0)
        self.world = self.client.get_world()
        self.scene = scene
        self.settings_before = self.world.get_settings()
        self.owned = []
        self.sensors = {}
        self.queues = {}
        self.signals = {}
        self.original_signal_state = {}
        self.ego = None
        self.index = -1
        self.last_frame = None
        self.last_time = None
        self.profile = None

    def configure_world(self, map_sha256, *, fixed_delta_seconds):
        need(fixed_delta_seconds == .05, "20 Hz Native clock required")
        native_map = self.world.get_map()
        need(native_map.name == self.scene.get("map_name"), "reviewed Native map name differs")
        observed_hash = hashlib.sha256(native_map.to_opendrive().encode()).hexdigest()
        need(observed_hash == map_sha256, "reviewed OpenDRIVE map hash differs")
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)

    def _location(self, xyz):
        return self.carla.Location(x=float(xyz[0]), y=float(xyz[1]),
                                   z=float(xyz[2]) if len(xyz) > 2 else 0.0)

    def spawn_ego(self, blueprint_id, spawn):
        need(str(blueprint_id).startswith("vehicle."), "motor-vehicle blueprint required")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        transform = self.carla.Transform(self._location(spawn),
                                         self.carla.Rotation(yaw=float(self.scene["approach_yaw_deg"])))
        actor = self.world.try_spawn_actor(blueprint, transform)
        need(actor is not None and actor.type_id == blueprint_id, "Native ego spawn failed")
        self.ego = actor
        self.owned.append(actor)
        return actor

    def _bind_signal(self, signal_id, route_id):
        need(route_id in {self.scene["selected_route_id"], self.scene.get("other_route_id")},
             "wrong surveyed route binding")
        actor = self.world.get_actor(int(signal_id))
        need(actor is not None and actor.type_id == "traffic.traffic_light",
             "official Native traffic light absent")
        affected = actor.get_affected_lane_waypoints()
        reviewed = (self.scene["other_route_native_lanes"] if
                    route_id == self.scene.get("other_route_id") else
                    self.scene["route_native_lanes"])
        need(any([waypoint.road_id, waypoint.lane_id] in reviewed
                 for waypoint in affected), "official head does not govern selected route")
        self.signals[str(signal_id)] = actor
        self.original_signal_state[str(signal_id)] = actor.get_state()
        return {"kind": "vehicular", "official": True, "facing_route_id": route_id,
                "source_sha256": (self.scene["other_route_device_sha256"]
                                  if str(signal_id) == str(self.scene.get("other_route_signal_id"))
                                  else self.scene["companion_device_sha256"]
                                  if str(signal_id) == str(self.scene.get("companion_signal_id"))
                                  else self.scene["official_device_sha256"]),
                "actor": actor}

    def bind_official_signal(self, signal_id, route_id):
        return self._bind_signal(signal_id, route_id)

    def bind_companion_signal(self, signal_id, route_id):
        return self._bind_signal(signal_id, route_id)

    def bind_other_route_signal(self, signal_id, route_id):
        return self._bind_signal(signal_id, route_id)

    def program_signal(self, signal, *, sequence, profile):
        need(sequence == ("green", "yellow", "red"), "wrong original signal sequence")
        signal["actor"].freeze(True)
        self.profile = profile

    def program_companion_signal(self, companion, *, active_during):
        need(active_during == "yellow", "companion lamp timing changed")
        companion["actor"].freeze(True)

    def program_other_route_signal(self, other, *, state):
        need(state == "red", "other-route comparison indication changed")
        other["actor"].freeze(True)

    def set_route_controller(self, ego, waypoints, *, behavior):
        need(len(waypoints) >= 3, "reviewed route missing")
        self.behavior = behavior
        self.route = [self._location(point) for point in waypoints]

    def attach_camera(self, ego, name):
        need(name in CAMERAS and name not in self.sensors, "unexpected or duplicate camera")
        from worker_exchange.capture import PROFILE
        if name == "overview":
            width, height = PROFILE["overview"]
        else:
            width, height = PROFILE["detail_views"][CAMERAS.index(name) - 1]
        blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
        blueprint.set_attribute("image_size_x", str(width))
        blueprint.set_attribute("image_size_y", str(height))
        blueprint.set_attribute("sensor_tick", "0.05")
        offset = {"overview": (-15, 0, 22), "approach": (-9, 4, 4),
                  "reference_corner": (5, 6, 7), "driver_reference": (0, 0, 2)}[name]
        sensor = self.world.spawn_actor(blueprint, self.carla.Transform(
            self.carla.Location(*offset)), attach_to=ego)
        queue = Queue()
        sensor.listen(queue.put)
        self.owned.append(sensor)
        self.sensors[name] = sensor
        self.queues[name] = queue

    def _phase(self):
        green_end = self.scene.get("green_end_frame", 100)
        yellow_end = self.scene.get("yellow_end_frame", 160)
        need(type(green_end) is int and type(yellow_end) is int and
             1 <= green_end < yellow_end < 900 and yellow_end - green_end <= 100,
             "reviewed phase schedule invalid")
        if self.index < green_end:
            return "green"
        return "yellow" if self.index < yellow_end else "red"

    def _control(self):
        ego = self.ego
        need(ego is not None, "Native ego missing")
        target = self.route[min(len(self.route) - 1, max(1, self.index // 150 + 1))]
        location = ego.get_location()
        yaw = ego.get_transform().rotation.yaw
        error = (heading_to(location, target) - yaw + 180) % 360 - 180
        steer = max(-.65, min(.65, error / 45))
        speed = ego.get_velocity()
        speed_mps = math.sqrt(speed.x * speed.x + speed.y * speed.y + speed.z * speed.z)
        target_speed = {"yellow": 9, "yellow_before_red": 9,
                        "red": 5, "other_route_red": 9,
                        "yellow_to_red": 8, "none": 0,
                        "companion_indication": 0}.get(self.profile, 7)
        if self.behavior == "stop_before_entry":
            vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
            ahead = max(vertices, key=lambda point: (point.x - location.x) *
                        math.cos(math.radians(yaw)) + (point.y - location.y) *
                        math.sin(math.radians(yaw)))
            distance = signed_distance(ahead.x, ahead.y,
                                       self.scene["intersection_polygon_xy"])
            if distance >= -max(4.0, speed_mps * 1.5):
                target_speed = 0
        throttle = max(0.0, min(.6, (target_speed - speed_mps) * .2))
        brake = max(0.0, min(.8, (speed_mps - target_speed) * .3))
        ego.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake,
                                                    steer=steer))

    def tick(self, built):
        self.index += 1
        phase = self._phase()
        selected = self.signals[str(self.scene["selected_signal_id"])]
        selected.set_state({"green": self.carla.TrafficLightState.Green,
                            "yellow": self.carla.TrafficLightState.Yellow,
                            "red": self.carla.TrafficLightState.Red}[phase])
        companion_id = self.scene.get("companion_signal_id")
        if self.profile == "companion_indication" and companion_id is not None:
            companion = self.signals[str(companion_id)]
            companion.set_state(self.carla.TrafficLightState.Green if phase == "yellow"
                                else self.carla.TrafficLightState.Red)
        other_id = self.scene.get("other_route_signal_id")
        if self.profile == "other_route_red" and other_id is not None:
            self.signals[str(other_id)].set_state(self.carla.TrafficLightState.Red)
        self._control()
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        need(snapshot.frame == frame, "Native world snapshot differs from tick")
        self.last_frame = frame
        self.last_time = snapshot.timestamp.elapsed_seconds
        return {"frame": frame, "time_s": self.last_time}

    def read_signal_row(self, frame, built, scene):
        need(frame == self.last_frame, "signal readback not from current Native frame")
        ego = self.ego
        vertices = ego.bounding_box.get_world_vertices(ego.get_transform())
        need(len(vertices) == 8, "ego body vertices missing")
        yaw = math.radians(ego.get_transform().rotation.yaw)
        forward = (math.cos(yaw), math.sin(yaw))
        center = ego.get_location()
        front = max(vertices, key=lambda point: (point.x - center.x) * forward[0] +
                    (point.y - center.y) * forward[1])
        selected_id = str(scene["selected_signal_id"])
        selected = self.signals[selected_id]
        velocity = ego.get_velocity()
        speed_mps = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        state = str(selected.get_state()).split(".")[-1].lower()
        need(state in {"green", "yellow", "red"}, "Native selected signal state invalid")
        companions = []
        companion_id = scene.get("companion_signal_id")
        if self.profile == "companion_indication" and companion_id is not None and state == "yellow":
            lamp = self.signals[str(companion_id)].get_state()
            if lamp == self.carla.TrafficLightState.Green:
                companions = [str(companion_id)]
        signals = [{"signal_id": selected_id,
                    "route_id": scene["selected_route_id"], "kind": "vehicular",
                    "official": True, "facing_ego": True, "state": state,
                    "flashing": False, "companion_lamps_on": companions,
                    "source": scene["official_device_source"]}]
        other_id = scene.get("other_route_signal_id")
        if self.profile == "other_route_red" and other_id is not None:
            other = self.signals[str(other_id)]
            signals.append({"signal_id": str(other_id), "route_id": scene["other_route_id"],
                            "kind": "vehicular", "official": True, "facing_ego": False,
                            "state": str(other.get_state()).split(".")[-1].lower(),
                            "source": scene["other_route_device_source"]})
        return {"origin": "native_world_snapshot", "native_frame": frame,
                "native_time_s": self.last_time,
                "heading_deg": ego.get_transform().rotation.yaw,
                "speed_mps": speed_mps,
                "ego_front_signed_distance_m": signed_distance(front.x, front.y,
                                                                  scene["intersection_polygon_xy"]),
                "ego_vertices": [[point.x, point.y, point.z] for point in vertices],
                "signals": signals}

    def read_cameras(self, frame, built):
        from PIL import Image
        result = {}
        for name in CAMERAS:
            image = None
            for _ in range(8):
                try:
                    candidate = self.queues[name].get(timeout=2)
                except Empty as error:
                    raise ValueError("Native camera frame absent: " + name) from error
                if candidate.frame == frame:
                    image = candidate
                    break
                need(candidate.frame < frame, "Native camera advanced past world frame")
            need(image is not None, "Native camera frame synchronization failed")
            raw = Image.frombytes("RGBA", (image.width, image.height),
                                  bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            buffer = BytesIO()
            raw.save(buffer, format="PNG")
            result[name] = {"frame": frame, "png": buffer.getvalue()}
        return result

    def source_bindings(self, scene):
        return {"intersection_polygon": scene["intersection_polygon_source"],
                "route_connectivity": scene["route_connectivity_source"],
                "device_route_binding": scene["device_route_binding_source"]}

    def brake(self):
        if self.ego is not None and self.ego.is_alive:
            self.ego.apply_control(self.carla.VehicleControl(throttle=0, brake=1))

    def destroy(self, actor):
        if getattr(actor, "is_alive", False):
            actor.destroy()

    def restore(self):
        for actor in reversed(self.owned):
            self.destroy(actor)
        for signal_id, actor in self.signals.items():
            if actor.is_alive:
                actor.set_state(self.original_signal_state[signal_id])
                actor.freeze(False)
        self.world.apply_settings(self.settings_before)


def create_adapter(host, port, scene):
    return CarlaSignalAdapter(host, port, scene)

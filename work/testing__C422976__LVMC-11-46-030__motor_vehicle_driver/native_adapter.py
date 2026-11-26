"""Source-gated Native capture for school-lane vehicle and warning actors.

The adapter records raw actor states and pixels. A later independent source
annotation is needed for human gestures, locality and legal classification.
"""

import hashlib
import json
import math
import queue
from pathlib import Path

from package_contract import CAMERAS
from school_lane_controls import selected_schedule
from warning_actuation import WarningActuator, require_sources


class NativeAdapter:
    def __init__(self, host, port, output_dir, scene):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.output_dir = Path(output_dir)
        self.scene = scene
        self.schedule = selected_schedule(scene["case_id"], scene["nearest_side_station_m"])
        self.world = None
        self.old_settings = None
        self.owned = []
        self.sensors = {}
        self.motion = []
        self.frame_map = []

    def _packet(self, name):
        root = Path(self.scene["authority_root"])
        ref = self.scene[name + "_source"]
        path = (root / ref["path"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("reviewed actor packet escapes authority root")
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref["sha256"]:
            raise ValueError("reviewed actor packet changed: " + name)
        return json.loads(path.read_text(encoding="utf-8"))

    def open_map(self):
        path = Path(self.scene["map_path"])
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.scene["opendrive_sha256"]:
            raise ValueError("reviewed original OpenDRIVE changed")
        self.world = self.client.generate_opendrive_world(data.decode("utf-8"))
        self.old_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        self.map = self.world.get_map()

    def _transform(self, packet, field):
        value = packet.get(field)
        if not isinstance(value, dict) or any(key not in value for key in ("x", "y", "z", "yaw")):
            raise ValueError("reviewed original actor pose required: " + field)
        numbers = [value[key] for key in ("x", "y", "z", "yaw")]
        if any(not isinstance(n, (int, float)) or not math.isfinite(n) for n in numbers):
            raise ValueError("finite reviewed actor pose required")
        return self.carla.Transform(
            self.carla.Location(x=value["x"], y=value["y"], z=value["z"]),
            self.carla.Rotation(yaw=value["yaw"]))

    def _spawn(self, packet, field, blueprint_prefix):
        blueprint_id = packet.get("blueprint_id")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith(blueprint_prefix):
            raise ValueError("reviewed Native blueprint required: " + blueprint_prefix)
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint, self._transform(packet, field))
        if actor is None:
            raise ValueError("reviewed original actor spawn failed")
        self.owned.append(actor)
        return actor

    def construct(self):
        vehicle = self._packet("vehicle_reference_point")
        human = self._packet("human_actor")
        device = self._packet("device_actor")
        child = self._packet("child_actor")
        if vehicle.get("reference_point") not in ("front_body_extent", "center", "rear_body_extent"):
            raise ValueError("reviewed vehicle body reference convention required")
        self.vehicle_reference = vehicle["reference_point"]
        self.ego = self._spawn(vehicle, "spawn_pose", "vehicle.")
        if self.scene["ego_approach_lane_id"] != self.map.get_waypoint(self.ego.get_location()).lane_id:
            raise ValueError("ego spawn differs from reviewed approach lane")
        self.human = self._spawn(human, "spawn_pose", "walker.pedestrian.")
        self.child = self._spawn(child, "spawn_pose", "walker.pedestrian.")
        actor_id = device.get("native_actor_id")
        self.device = self.world.get_actor(actor_id) if isinstance(actor_id, int) else None
        if self.device is None:
            raise ValueError("reviewed original school warning device unavailable")
        self.warning_packet = human
        self.device_packet = device
        kind = self.schedule["requested_warning_actor"]
        require_sources(self.schedule, human, device, child)
        self.flag = None
        if kind in ("human", "human_present"):
            flag = {"blueprint_id": human["flag_blueprint_id"],
                    "spawn_pose": human["flag_parked_pose"]}
            self.flag = self._spawn(flag, "spawn_pose", "static.prop.")
        self.warning = WarningActuator(self.schedule, human, device, child, self)
        for camera in CAMERAS:
            packet = vehicle.get("camera_poses", {}).get(camera["name"])
            if not isinstance(packet, dict):
                raise ValueError("reviewed original four-camera pose required")
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            transform = self._transform({"camera": packet}, "camera")
            sensor = self.world.spawn_actor(blueprint, transform)
            if sensor is None:
                raise ValueError("reviewed camera spawn failed")
            self.owned.append(sensor)
            received = queue.Queue(maxsize=4)
            sensor.listen(received.put)
            self.sensors[camera["name"]] = received

    def tick_and_capture(self, index):
        self.warning.request(index)
        target = self.schedule["ego_stop_reference_station_target_m"]
        location = self.ego.get_location()
        station = location.x
        speed = math.sqrt(sum(x*x for x in (self.ego.get_velocity().x,
                                            self.ego.get_velocity().y,
                                            self.ego.get_velocity().z)))
        release = self.schedule["release_frame"]
        if self.schedule["requested_ego_response"] == "travel":
            throttle, brake = .25, 0.0
        elif target is not None and station < target - max(1.0, speed * speed / 8):
            throttle, brake = .25, 0.0
        elif target is not None and station < target - .25:
            throttle, brake = 0.0, .65
        elif self.schedule["requested_ego_response"] == "premature" and index >= 400:
            throttle, brake = .25, 0.0
        elif release is not None and index >= release and self.schedule["requested_ego_response"] == "proceed":
            throttle, brake = .25, 0.0
        else:
            throttle, brake = 0.0, 1.0
        self.ego.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake))
        native_frame = self.world.tick()
        frames = {}
        for name, received in self.sensors.items():
            image = received.get(timeout=20)
            if image.frame != native_frame:
                raise ValueError("original four-camera frame join failed")
            path = self.output_dir / "capture" / name / f"{index:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            frames[name] = {"native_frame": image.frame,
                            "path": str(path.relative_to(self.output_dir)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        actual = self.ego.get_location()
        velocity = self.ego.get_velocity()
        row = {"frame": index, "time_s": index/20, "native_frame": native_frame,
               "ego_actor_id": self.ego.id,
               "ego_reference_station_m": actual.x,
               "ego_speed_mps": math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2),
               "human_actor_id": self.human.id, "human_xyz": [self.human.get_location().x,
                   self.human.get_location().y, self.human.get_location().z],
               "child_actor_id": self.child.id,
               "device_actor_id": self.device.id,
               "device_type_id": self.device.type_id,
               "actor_state_readback": self.warning.readback(),
               "requested_controls": {"warning_on_from_frame": self.schedule["warning_on_from_frame"],
                                      "release_frame": release,
                                      "ego_throttle": throttle, "ego_brake": brake}}
        self.motion.append(row)
        self.frame_map.append({"frame": index, "time_s": index/20,
                               "native_frame": native_frame, "camera_frames": frames})

    def set_flag_pose(self, pose):
        if self.flag is None:
            raise ValueError("reviewed Native flag actor unavailable")
        self.flag.set_transform(self._transform({"pose": pose}, "pose"))

    def read_flag_pose(self):
        if self.flag is None:
            return None
        transform = self.flag.get_transform()
        return {"x": transform.location.x, "y": transform.location.y,
                "z": transform.location.z, "yaw": transform.rotation.yaw}

    def set_device_state(self, state):
        if not hasattr(self.device, "set_state") or not hasattr(self.device, "get_state"):
            raise ValueError("reviewed Native school warning device lacks state readback")
        if state not in ("Red", "Off", "Green", "Yellow"):
            raise ValueError("reviewed device state is not a Native state")
        self.device.set_state(getattr(self.carla.TrafficLightState, state))

    def read_device_state(self):
        return str(self.device.get_state()) if hasattr(self.device, "get_state") else None

    def _move_walker(self, actor, velocity):
        if not isinstance(velocity, list) or len(velocity) != 2 or any(
                not isinstance(v, (int, float)) or not math.isfinite(v) for v in velocity):
            raise ValueError("reviewed finite walker motion required")
        speed = math.hypot(*velocity)
        if speed <= 0 or speed > 3.0:
            raise ValueError("reviewed walker speed outside bounded actuation")
        actor.apply_control(self.carla.WalkerControl(
            direction=self.carla.Vector3D(velocity[0]/speed, velocity[1]/speed, 0),
            speed=speed))

    def move_human(self, velocity):
        self._move_walker(self.human, velocity)

    def move_child(self, velocity):
        self._move_walker(self.child, velocity)

    def read_human_location(self):
        location = self.human.get_location()
        return [location.x, location.y, location.z]

    def read_child_location(self):
        location = self.child.get_location()
        return [location.x, location.y, location.z]

    def close(self):
        if self.motion:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "original-motion.json").write_text(
                json.dumps({"source_kind": "original_native_raw", "case_id": self.scene["case_id"],
                            "frames": self.motion}) + "\n", encoding="utf-8")
            (self.output_dir / "original-frame-map.json").write_text(
                json.dumps({"source_kind": "original_native_frame_map", "case_id": self.scene["case_id"],
                            "frames": self.frame_map}) + "\n", encoding="utf-8")
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
            finally:
                actor.destroy()
        if self.world is not None and self.old_settings is not None:
            self.world.apply_settings(self.old_settings)

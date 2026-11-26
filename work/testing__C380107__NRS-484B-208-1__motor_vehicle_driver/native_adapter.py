"""Original CARLA actor, lane and four-view capture with source-gated controls."""

import hashlib
import json
import math
import queue
from pathlib import Path

from package_contract import CAMERAS


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class NativeAdapter:
    def __init__(self, host, port, output_dir, scene):
        import carla
        self.carla = carla
        self.client = carla.Client(host, port)
        self.client.set_timeout(30.0)
        self.output_dir = Path(output_dir)
        self.scene = scene
        self.world = None
        self.previous_settings = None
        self.owned = []
        self.sensors = {}
        self.rows = []
        self.frame_map = []
        self.sign = None

    def open_map(self):
        path = Path(self.scene["map_path"])
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != self.scene["source_refs"]["opendrive"]["sha256"]:
            raise ValueError("reviewed original OpenDRIVE bytes changed")
        self.world = self.client.generate_opendrive_world(data.decode("utf-8"))
        self.previous_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        self.map = self.world.get_map()

    def _transform(self, pose):
        if not isinstance(pose, dict) or any(not finite(pose.get(k)) for k in ("x", "y", "z", "yaw")):
            raise ValueError("finite reviewed original Native pose required")
        return self.carla.Transform(self.carla.Location(x=pose["x"], y=pose["y"], z=pose["z"]),
                                    self.carla.Rotation(yaw=pose["yaw"]))

    def _spawn(self, record, prefix):
        blueprint_id = record.get("blueprint_id")
        if not isinstance(blueprint_id, str) or not blueprint_id.startswith(prefix):
            raise ValueError("reviewed original Native blueprint required")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(blueprint, self._transform(record.get("spawn_pose")))
        if actor is None:
            raise ValueError("reviewed original Native actor spawn failed")
        self.owned.append(actor)
        return actor

    def _lane(self, actor):
        waypoint = self.map.get_waypoint(actor.get_location(), project_to_road=False)
        if waypoint is None:
            raise ValueError("original vehicle absent from reviewed lane geometry")
        return str(waypoint.lane_id), waypoint

    def construct(self):
        poses = self.scene["actor_poses"]
        self.ego = self._spawn(poses["ego"], "vehicle.")
        self.rear = self._spawn(poses["rear"], "vehicle.")
        ego_lane, _ = self._lane(self.ego)
        rear_lane, _ = self._lane(self.rear)
        if ego_lane != str(self.scene["extreme_left_lane_id"]) or rear_lane != ego_lane:
            raise ValueError("original ego/rear spawn does not match extreme-left lane")
        count = poses.get("reviewed_original_occupant_count")
        if count != self.scene["schedule"]["hov_occupancy_target"]:
            raise ValueError("reviewed original occupant count does not realize selected engineering request")
        sign_record = poses.get("sign_actor")
        if not isinstance(sign_record, dict) or not str(sign_record.get("blueprint_id", "")).startswith("static.prop."):
            raise ValueError("source-gated original posted-limit/HOV sign actor required")
        self.sign_record = sign_record
        for camera in CAMERAS:
            pose = poses["camera_poses"][camera["name"]]
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            blueprint.set_attribute("image_size_x", str(camera["width"]))
            blueprint.set_attribute("image_size_y", str(camera["height"]))
            blueprint.set_attribute("fov", str(camera["fov_deg"]))
            sensor = self.world.spawn_actor(blueprint, self._transform(pose))
            if sensor is None:
                raise ValueError("original camera spawn failed")
            self.owned.append(sensor)
            frames = queue.Queue(maxsize=4)
            sensor.listen(frames.put)
            self.sensors[camera["name"]] = frames

    @staticmethod
    def _speed(actor):
        velocity = actor.get_velocity()
        return math.sqrt(velocity.x**2 + velocity.y**2 + velocity.z**2)

    def _control_speed(self, actor, target, steer=0.0):
        delta = target - self._speed(actor)
        throttle = min(.55, max(0.0, .15 + .13 * delta)) if delta > .1 else 0.0
        brake = min(.65, max(0.0, -.15 * delta)) if delta < -.1 else 0.0
        actor.apply_control(self.carla.VehicleControl(throttle=throttle, brake=brake, steer=steer))
        return {"target_speed_mps": target, "throttle": throttle, "brake": brake, "steer": steer}

    def _right_steer(self, frame):
        if self.scene["schedule"]["ego_response_request"] != "move_right" or frame < 240:
            return 0.0
        lane_id, waypoint = self._lane(self.ego)
        if lane_id == str(self.scene["right_response_lane_id"]):
            return 0.0
        right = waypoint.get_right_lane()
        if right is None or str(right.lane_id) != str(self.scene["right_response_lane_id"]):
            raise ValueError("reviewed adjacent right response lane unavailable")
        target = right.transform.location
        position = self.ego.get_location()
        yaw = math.radians(self.ego.get_transform().rotation.yaw)
        lateral = -math.sin(yaw) * (target.x - position.x) + math.cos(yaw) * (target.y - position.y)
        return max(-.35, min(.35, .12 * lateral))

    def tick_and_capture(self, index):
        if index == self.scene["schedule"]["sign_exposure_start_frame"]:
            self.sign = self._spawn(self.sign_record, "static.prop.")
        ego_control = self._control_speed(self.ego, self.scene["schedule"]["ego_target_speed_mps"], self._right_steer(index))
        rear_control = self._control_speed(self.rear, self.scene["schedule"]["rear_target_speed_mps"])
        native_frame = self.world.tick()
        camera_frames = {}
        for name, frame_queue in self.sensors.items():
            image = frame_queue.get(timeout=20)
            if image.frame != native_frame:
                raise ValueError("original four-camera frame join failed")
            path = self.output_dir / "capture" / name / f"{index:06d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save_to_disk(str(path))
            camera_frames[name] = {"native_frame": image.frame,
                                   "path": str(path.relative_to(self.output_dir)),
                                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        ego_lane, _ = self._lane(self.ego)
        rear_lane, _ = self._lane(self.rear)
        ego_location, rear_location = self.ego.get_location(), self.rear.get_location()
        yaw = math.radians(self.ego.get_transform().rotation.yaw)
        gap = math.cos(yaw) * (ego_location.x - rear_location.x) + math.sin(yaw) * (ego_location.y - rear_location.y)
        self.rows.append({"frame": index, "time_s": index / 20, "native_frame": native_frame,
                          "ego_actor_id": self.ego.id, "rear_actor_id": self.rear.id,
                          "ego_lane_id": ego_lane, "rear_lane_id": rear_lane,
                          "ego_speed_mps": self._speed(self.ego), "rear_speed_mps": self._speed(self.rear),
                          "rear_to_ego_signed_gap_m": gap,
                          "sign_actor_id": self.sign.id if self.sign is not None else None,
                          "sign_present_readback": self.sign is not None and self.sign.is_alive,
                          "reviewed_original_occupant_count": self.scene["actor_poses"]["reviewed_original_occupant_count"],
                          "requested_ego_control": ego_control, "requested_rear_control": rear_control})
        self.frame_map.append({"frame": index, "time_s": index / 20,
                               "native_frame": native_frame, "camera_frames": camera_frames})

    def close(self):
        if self.rows:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            (self.output_dir / "original-motion.jsonl").write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in self.rows) + "\n", encoding="utf-8")
            (self.output_dir / "original-frame-map.json").write_text(
                json.dumps({"source_kind": "original_native_frame_map", "case_id": self.scene["case_id"],
                            "frames": self.frame_map}, sort_keys=True) + "\n", encoding="utf-8")
            (self.output_dir / "original-site-ref.json").write_text(
                json.dumps({"source_kind": "reviewed_original_site", "case_id": self.scene["case_id"],
                            "site_path": self.scene["site_path"], "site_sha256": self.scene["site_sha256"],
                            "source_refs": self.scene["source_refs"]}, sort_keys=True) + "\n", encoding="utf-8")
        for actor in reversed(self.owned):
            try:
                if hasattr(actor, "stop"):
                    actor.stop()
            finally:
                actor.destroy()
        if self.world is not None and self.previous_settings is not None:
            self.world.apply_settings(self.previous_settings)

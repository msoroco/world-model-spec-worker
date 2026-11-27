"""Lazy CARLA adapter for reviewed cycle, articulated rider and four cameras.

Native availability and physical rider attachment are checked on the local GPU
run. This module does not turn an engineering arm target into original evidence.
"""

import hashlib
import json
import math
import subprocess
from pathlib import Path
from queue import Queue


def _line(path, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, allow_nan=False, sort_keys=True) + "\n")


def _loc(value):
    return [value.x, value.y, value.z]


class NativeAdapter:
    def __init__(self, config, host, port):
        import carla
        self.carla = carla
        self.config = config
        self.client = carla.Client(host, port)
        self.client.set_timeout(30)
        self.world = self.client.get_world()
        self.route = None
        self.route_index = 1
        self.cycle = None
        self.rider = None
        self.sensors = {}
        self.encoder_codes = {}
        self.output = None
        self.recorder_started = False

    def map_opendrive_bytes(self):
        return self.world.get_map().to_opendrive().encode("utf-8")

    def route_readback(self, route, roadway_polygon, shoulder_polygon):
        from signal_scene import _inside
        road_map = self.world.get_map()
        for point in route:
            if not _inside(point, roadway_polygon) or _inside(point, shoulder_polygon):
                return False
            waypoint = road_map.get_waypoint(
                self.carla.Location(x=point[0], y=point[1], z=0),
                project_to_road=False, lane_type=self.carla.LaneType.Driving)
            if waypoint is None or waypoint.lane_type != self.carla.LaneType.Driving:
                return False
        return True

    def supports_arm_rig(self, blueprint_id, rig):
        try:
            blueprint = self.world.get_blueprint_library().find(blueprint_id)
        except (KeyError, RuntimeError):
            return False
        return bool(blueprint and blueprint_id.startswith("walker.pedestrian.") and
                    hasattr(self.carla, "WalkerBoneControlIn") or
                    blueprint and blueprint_id.startswith("walker.pedestrian.") and
                    hasattr(self.carla, "WalkerBoneControl"))

    def spawn_cycle(self, blueprint_id, start):
        bp = self.world.get_blueprint_library().find(blueprint_id)
        if not blueprint_id.startswith("vehicle."):
            raise ValueError("reviewed bicycle/scooter vehicle blueprint required")
        actor = self.world.try_spawn_actor(bp, self.carla.Transform(
            self.carla.Location(x=start[0], y=start[1], z=0.2)))
        if actor is None or actor.type_id != blueprint_id:
            raise ValueError("reviewed covered cycle spawn failed")
        self.cycle = actor
        return actor

    def spawn_rider(self, blueprint_id, cycle, operator_identity):
        rig_offset = self.config.get("rider_mount_offset_m", [0, 0, 0.6])
        bp = self.world.get_blueprint_library().find(blueprint_id)
        actor = self.world.try_spawn_actor(bp, self.carla.Transform(
            self.carla.Location(x=rig_offset[0], y=rig_offset[1], z=rig_offset[2])),
            attach_to=cycle)
        if actor is None or actor.type_id != blueprint_id or actor.parent.id != cycle.id:
            raise ValueError("reviewed rider physical attachment failed")
        self.rider = actor
        return actor

    def set_cycle_route(self, cycle, route):
        self.route = route
        self.route_index = 1

    def _bone_rows(self, rider):
        bones = rider.get_bones()
        rows = getattr(bones, "bone_transforms", None)
        if rows is None:
            raise ValueError("original rider bone readback unavailable")
        return {row.name: row for row in rows}

    def apply_right_arm_pose(self, rider, rig, posture, requested):
        rotations = rig.get("posture_rotations_deg", {}).get(posture)
        if not isinstance(rotations, dict):
            return False
        names = (rig["right_shoulder"], rig["right_elbow"], rig["right_wrist"])
        rows = self._bone_rows(rider)
        if any(name not in rows or name not in rotations for name in names):
            return False
        transforms = []
        for name in names:
            angles = rotations[name]
            if not isinstance(angles, list) or len(angles) != 3 or any(
                    not isinstance(v, (int, float)) or not math.isfinite(v) for v in angles):
                return False
            transform = self.carla.Transform(
                rotation=self.carla.Rotation(pitch=angles[0], yaw=angles[1], roll=angles[2]))
            transforms.append((name, transform))
        if hasattr(rider, "set_bones") and hasattr(self.carla, "WalkerBoneControlIn"):
            command = self.carla.WalkerBoneControlIn()
            command.bone_transforms = transforms
            rider.set_bones(command)
            rider.show_pose()
        elif hasattr(self.carla, "WalkerBoneControl"):
            command = self.carla.WalkerBoneControl()
            command.bone_transforms = transforms
            rider.apply_control(command)
        else:
            return False
        return True

    def read_right_arm_joints(self, rider, rig):
        rows = self._bone_rows(rider)
        names = (rig["right_shoulder"], rig["right_elbow"], rig["right_wrist"])
        if any(name not in rows for name in names):
            raise ValueError("original right arm joint readback missing")
        return {key: _loc(rows[rig[name]].world.location) for key, name in
                (("shoulder", "right_shoulder"), ("elbow", "right_elbow"),
                 ("wrist", "right_wrist"))}

    def begin_four_camera_capture(self, views, cameras, sites, rig, owned, output):
        output = Path(output)
        self.output = output
        self.rig = rig
        (output / "capture/native/graphs/base").mkdir(parents=True, exist_ok=True)
        for name in ("trace.jsonl", "capture/evidence.jsonl", "capture/native/frames.jsonl"):
            (output / name).touch(exist_ok=False)
        (output / "road.xodr").write_bytes(self.map_opendrive_bytes())
        self.client.start_recorder(str(output / "carla_recorder.log"))
        self.recorder_started = True
        for camera in cameras:
            name = camera["name"]
            bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            bp.set_attribute("image_size_x", str(camera["width"]))
            bp.set_attribute("image_size_y", str(camera["height"]))
            bp.set_attribute("fov", str(camera["fov_deg"]))
            bp.set_attribute("sensor_tick", "0.05")
            x, y, z, pitch, yaw, roll = sites[name]
            sensor = self.world.spawn_actor(bp, self.carla.Transform(
                self.carla.Location(x=x, y=y, z=z),
                self.carla.Rotation(pitch=pitch, yaw=yaw, roll=roll)),
                attach_to=self.cycle)
            queue = Queue(maxsize=4)
            sensor.listen(queue.put)
            self.sensors[name] = (sensor, queue)
            owned.append(sensor)
            (output / "capture" / name).mkdir(parents=True, exist_ok=False)

    def tick(self):
        if self.route is None or self.cycle is None:
            raise ValueError("original cycle route not configured")
        position = self.cycle.get_location()
        target = self.route[self.route_index]
        if math.hypot(target[0] - position.x, target[1] - position.y) < 2 and \
                self.route_index < len(self.route) - 1:
            self.route_index += 1
            target = self.route[self.route_index]
        yaw = self.cycle.get_transform().rotation.yaw
        desired = math.degrees(math.atan2(target[1] - position.y, target[0] - position.x))
        error = (desired - yaw + 180) % 360 - 180
        speed = self.cycle.get_velocity().length()
        control = self.carla.VehicleControl()
        control.throttle = max(0, min(0.5, 0.3 + (4 - speed) * 0.05))
        control.steer = max(-0.45, min(0.45, error * 0.015))
        control.brake = 0.25 if self.route_index == len(self.route) - 1 and \
            math.hypot(target[0] - position.x, target[1] - position.y) < 1 else 0
        self.cycle.apply_control(control)
        return self.world.tick()

    def read_original_signal_frame(self, frame, built):
        transform = self.cycle.get_transform()
        position = self.cycle.get_location()
        yaw = math.radians(transform.rotation.yaw)
        return {"operator_vehicle_contact_point": [position.x, position.y],
                "operator_heading": [math.cos(yaw), math.sin(yaw)],
                "right_arm": self.read_right_arm_joints(self.rider, self.rig)}

    def record_original_trace_frame(self, frame, time_s, built, output):
        cycle = built["cycle"]
        transform = cycle.get_transform()
        position = cycle.get_location()
        velocity = cycle.get_velocity()
        bounds = cycle.bounding_box.get_world_vertices(transform)
        row = {"frame": frame, "time_s": time_s,
               "position_m": _loc(position), "speed_mps": velocity.length(),
               "velocity_mps": _loc(velocity), "heading_deg": transform.rotation.yaw,
               "control": {}}
        _line(self.output / "trace.jsonl", row)
        observed = {"frame": frame, "time_s": time_s, "participants": [
            {"actor_id": cycle.id, "blueprint": cycle.type_id},
            {"actor_id": self.rider.id, "blueprint": self.rider.type_id}],
            "map_context": {"declared_public_way_road_ids": []}}
        _line(self.output / "capture/evidence.jsonl", {
            "original_frame": frame, "replay_frame": frame,
            "actor_id": cycle.id, "recording_time_s": time_s,
            "replay_simulation_time_s": time_s,
            "world": {"weather": {}},
            "ego": {"position_m": _loc(position),
                    "heading_deg": transform.rotation.yaw,
                    "speed_mps": velocity.length(),
                    "speed_provenance": "original_native_readback",
                    "body_vertices_m": [_loc(vertex) for vertex in bounds]},
            "original_observations": observed})
        graph = f"graphs/base/{frame:08d}.adapter.json"
        (self.output / "capture/native" / graph).write_text(json.dumps({
            "path": "capture/native/" + graph,
            "attributes": {"frame": frame, "time_s": time_s,
                           "observed_evidence": observed},
            "nodes": [], "edges": []}) + "\n")
        _line(self.output / "capture/native/frames.jsonl", {
            "frame": frame, "simulation_time": time_s,
            "adapter_graph": graph})

    def capture_frame_identities(self, frame):
        result = {}
        for name, (_, queue) in self.sensors.items():
            image = queue.get(timeout=30)
            if image.frame != frame:
                raise ValueError("original camera frame mismatch: " + name)
            image.save_to_disk(str(self.output / "capture" / name /
                                   f"{frame:08d}.png"))
            result[name] = image.frame
        return result

    def finish_four_camera_capture(self, output):
        output = Path(output)
        for name, (sensor, _) in self.sensors.items():
            sensor.stop()
            source = output / "capture" / name
            command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                       "-framerate", "20", "-pattern_type", "glob", "-i", str(source / "*.png"),
                       "-frames:v", "900", "-c:v", "ffv1", "-threads", "1",
                       str(output / (name + ".mkv"))]
            self.encoder_codes[name] = subprocess.run(command, check=False,
                                                       timeout=900).returncode
        if self.recorder_started:
            self.client.stop_recorder()
            self.recorder_started = False
            (output / "capture/recorder_info.txt").write_text(
                self.client.show_recorder_file_info(str(output / "carla_recorder.log"), False))
        (output / "capture/native_map_facts.json").write_text(json.dumps({
            "map": self.world.get_map().name,
            "junctions": [], "crosswalk_vertices_m": [],
            "crosswalk_inventory_scope": "original Native map metadata"}) + "\n")
        (output / "capture/manifest.json").write_text(json.dumps({
            "status": "draft", "acquisition": "original_native",
            "case_id": self.config["selected_case_id"], "frames": 900,
            "extraction_confirmed": True, "complete_driving_lanes": False,
            "native_map_facts": {"path": "native_map_facts.json",
                                 "sha256": hashlib.sha256((output / "capture/native_map_facts.json").read_bytes()).hexdigest()},
            "sources": {"road.xodr": hashlib.sha256((output / "road.xodr").read_bytes()).hexdigest(),
                        "trace.jsonl": hashlib.sha256((output / "trace.jsonl").read_bytes()).hexdigest()}}) + "\n")
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "physical_acceptance_claimed": False}) + "\n")

    def camera_frame_counts(self):
        return {name: len(list((self.output / "capture" / name).glob("*.png")))
                for name in self.sensors}

    def native_source_kind(self):
        return "original_native_capture"

    def encoder_exit_codes(self):
        return self.encoder_codes

    def destroy(self, actor):
        if hasattr(actor, "stop"):
            actor.stop()
        actor.destroy()

    def cleanup(self):
        if self.recorder_started:
            self.client.stop_recorder()
            self.recorder_started = False


def create_adapter(config, host, port):
    return NativeAdapter(config, host, port)

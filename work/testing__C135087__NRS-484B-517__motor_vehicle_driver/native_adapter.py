"""Lazy CARLA session for source-bound C135087 capture.

Control schedules are authored inputs. Every exported observation is read from
live actors, sensors, map and snapshots; none is a legal judgment.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import threading
import time

from stand import SourceError, _inside_polygon

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def _require(ok, message):
    if not ok:
        raise SourceError(message)


def _json(path, value):
    path = Path(path)
    _require(not path.exists(), "refusing to overwrite original converter source: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, allow_nan=False) + "\n")


def _lines(path, values):
    path = Path(path)
    _require(not path.exists(), "refusing to overwrite original converter source: " + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(v, sort_keys=True, allow_nan=False) + "\n" for v in values))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_native_sources(site, vehicles):
    """Check the extra original bindings before a world can be changed."""
    native = site.get("native_binding") if isinstance(site, dict) else None
    _require(isinstance(native, dict), "reviewed Native stand binding missing")
    for key in ("sign_actor_id", "sign_blueprint", "curb_actor_id", "curb_blueprint",
                "passenger_blueprint", "camera_transforms", "access_polygon",
                "observation", "control"):
        _require(native.get(key) not in (None, "", [], {}), "reviewed Native binding missing: " + key)
    _require(set(native["camera_transforms"]) == set(VIEWS), "four reviewed camera poses required")
    for name, pose in native["camera_transforms"].items():
        _require(isinstance(pose, dict) and len(pose.get("location_m", [])) == 3 and
                 len(pose.get("rotation_deg", [])) == 3 and
                 all(math.isfinite(float(x)) for x in pose["location_m"] + pose["rotation_deg"]),
                 "invalid reviewed camera pose: " + name)
    _require(len(native["access_polygon"]) >= 3, "reviewed entrant access polygon missing")
    for key in ("loading_radius_m", "entry_range_m", "motion_epsilon_mps"):
        value = native["observation"].get(key)
        _require(value is not None and math.isfinite(float(value)) and
                 float(value) > 0,
                 "reviewed Native observation parameter missing: " + key)
    control = native["control"]
    for key in ("approach_frames", "loading_frames", "entrant_start_frame",
                "subject_throttle", "passenger_speed_mps", "entrant_throttle"):
        _require(key in control, "reviewed Native control parameter missing: " + key)
    _require(isinstance(vehicles, dict) and vehicles.get("subject") and vehicles.get("entrant"),
             "reviewed Native vehicle roles missing")
    return native


class _Encoder:
    def __init__(self, path, width, height):
        self.process = subprocess.Popen([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
            "-pixel_format", "bgra", "-video_size", f"{width}x{height}",
            "-framerate", "20", "-i", "pipe:0", "-an", "-c:v", "libx264",
            "-preset", "veryfast", "-pix_fmt", "yuv420p", str(path)],
            stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        self.pending = queue.Queue(maxsize=8)
        self.error = None
        self.completed = False
        self.worker = threading.Thread(target=self._write, daemon=True)
        self.worker.start()

    def _write(self):
        try:
            while True:
                packet = self.pending.get()
                if packet is None:
                    break
                self.process.stdin.write(packet)
            self.process.stdin.close()
        except (BrokenPipeError, OSError) as error:
            self.error = error

    def feed(self, raw):
        self.pending.put(bytes(raw), timeout=60)

    def finish(self):
        self.pending.put(None, timeout=60)
        self.worker.join(timeout=180)
        _require(not self.worker.is_alive(), "original RGB encoder did not finish")
        stderr = self.process.stderr.read()
        code = self.process.wait(timeout=60)
        _require(self.error is None and code == 0,
                 "original RGB encoder failed: " + stderr.decode(errors="replace")[-500:])
        self.completed = True

    def abort(self):
        if self.completed:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        try:
            self.pending.put_nowait(None)
        except queue.Full:
            pass
        self.worker.join(timeout=5)
        _require(not self.worker.is_alive(), "original RGB encoder abort did not finish")
        self.process.stderr.close()


class Session:
    def __init__(self, host, port, config, *, carla_module=None, client_factory=None,
                 encoder_factory=None):
        self.host, self.port, self.config = host, int(port), config
        self.carla = carla_module
        self.client_factory = client_factory
        self.encoder_factory = encoder_factory or _Encoder
        self.owned = []
        self.sensors = {}
        self.encoders = {}
        self.finished_encoders = set()
        self.frames = []
        self.camera_frames = {name: [] for name in VIEWS}
        self.camera_errors = []
        self.restoration_verified = False
        self.site = None
        self.native = None
        self.actors = {}
        self.adapter = self

    def __enter__(self):
        if self.carla is None:
            import carla
            self.carla = carla
        self.client = (self.client_factory or self.carla.Client)(self.host, self.port)
        self.client.set_timeout(30.0)
        self.world = self.client.get_world()
        self.mapping = self.world.get_map()
        self.original_settings = self.world.get_settings()
        return self

    def __exit__(self, exc_type, exc, traceback):
        errors = []
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except Exception as error:
                errors.append(str(error))
        for name, encoder in self.encoders.items():
            if name not in self.finished_encoders:
                try:
                    encoder.abort()
                except Exception as error:
                    errors.append("RGB encoder " + name + ": " + str(error))
        for actor in reversed(self.owned):
            try:
                actor.destroy()
            except Exception as error:
                errors.append(str(error))
        try:
            self.world.apply_settings(self.original_settings)
            self.restoration_verified = (self.world.get_settings().synchronous_mode ==
                                         self.original_settings.synchronous_mode and
                                         self.world.get_settings().fixed_delta_seconds ==
                                         self.original_settings.fixed_delta_seconds)
        except Exception as error:
            errors.append(str(error))
        if errors or not self.restoration_verified:
            raise SourceError("Native world/sensor restoration failed: " + "; ".join(errors))
        return False

    def _actor(self, actor_id, blueprint):
        actor = self.world.get_actors().find(int(actor_id))
        _require(actor is not None and actor.type_id == blueprint,
                 "reviewed Native sign/curb actor readback differs")
        return actor

    def verify_site(self, site):
        _require(self.mapping.name == site["map_name"], "reviewed Native map differs")
        native = validate_native_sources(site, {"subject": 1, "entrant": 1})
        self._actor(native["sign_actor_id"], native["sign_blueprint"])
        curb = self._actor(native["curb_actor_id"], native["curb_blueprint"])
        vertices = curb.bounding_box.get_world_vertices(curb.get_transform())
        observed = sorted({(round(float(v.x), 2), round(float(v.y), 2)) for v in vertices})
        expected = sorted({(round(float(p[0]), 2), round(float(p[1]), 2))
                           for p in site["curb_polygon"]})
        _require(observed == expected, "Native curb polygon readback differs")
        self.site, self.native = site, native
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = .05
        self.world.apply_settings(settings)
        _require(self.world.get_settings().synchronous_mode and
                 abs(self.world.get_settings().fixed_delta_seconds - .05) < 1e-9,
                 "Native world did not enter synchronous 20 Hz")
        return {"map_name": self.mapping.name, "sign_visible": True,
                "sign_id": site["sign_id"], "curb_polygon": site["curb_polygon"]}

    def _spawn(self, blueprint_name, point, *, road=True):
        blueprint = self.world.get_blueprint_library().find(blueprint_name)
        location = self.carla.Location(x=float(point[0]), y=float(point[1]), z=0.0)
        waypoint = self.mapping.get_waypoint(location, project_to_road=road)
        _require(waypoint is not None, "reviewed Native spawn point has no waypoint")
        transform = waypoint.transform
        actor = self.world.try_spawn_actor(blueprint, transform)
        _require(actor is not None and actor.type_id == blueprint_name,
                 "Native participant spawn or blueprint readback failed")
        self.owned.append(actor)
        return actor

    def spawn_subject(self, role, point):
        actor = self._spawn(role["blueprint"], point)
        self.actors["subject"] = actor
        return {"actor_id": actor.id, "blueprint": actor.type_id}

    def spawn_entrant(self, role, waypoints, mode):
        actor = self._spawn(role["blueprint"], waypoints[0])
        self.actors["entrant"] = actor
        self.entrant_mode = mode
        return {"actor_id": actor.id, "blueprint": actor.type_id}

    def spawn_passenger(self, point):
        actor = self._spawn(self.native["passenger_blueprint"], point)
        self.actors["passenger"] = actor
        return {"actor_id": actor.id}

    def configure_loading(self, subject_id, passenger_id, mode):
        _require(self.actors["subject"].id == subject_id and
                 self.actors["passenger"].id == passenger_id,
                 "Native loading actor identity differs")
        self.loading_mode = mode

    def configure_access(self, entrant_id, waypoints, mode):
        _require(self.actors["entrant"].id == entrant_id,
                 "Native entrant actor identity differs")
        self.access_mode = mode

    def start_cameras(self, root, cameras, constructed):
        _require(self.site is not None and set(self.actors) ==
                 {"subject", "entrant", "passenger"}, "Native construction incomplete")
        self.root = Path(root)
        _require(set(c["name"] for c in cameras) == set(VIEWS), "four RGB views required")
        for spec in cameras:
            name = spec["name"]
            blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
            for key, value in (("image_size_x", spec["width"]),
                               ("image_size_y", spec["height"]),
                               ("fov", spec["fov_deg"]), ("sensor_tick", 0)):
                blueprint.set_attribute(key, str(value))
            pose = self.native["camera_transforms"][name]
            x, y, z = pose["location_m"]
            pitch, yaw, roll = pose["rotation_deg"]
            transform = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                             self.carla.Rotation(pitch=pitch, yaw=yaw, roll=roll))
            sensor = self.world.spawn_actor(blueprint, transform)
            _require(sensor is not None and sensor.type_id == "sensor.camera.rgb",
                     "Native RGB sensor spawn failed")
            self.owned.append(sensor)
            self.sensors[name] = sensor
            encoder = self.encoder_factory(self.root / (name + ".mkv"), spec["width"], spec["height"])
            self.encoders[name] = encoder
            def receive(image, view=name, sink=encoder):
                try:
                    sink.feed(image.raw_data)
                    self.camera_frames[view].append((image.frame, float(image.timestamp)))
                except Exception as error:
                    self.camera_errors.append(f"{view}: {error}")
            sensor.listen(receive)

    def step(self, world, actors, index):
        _require(world is self.world and actors == self.actors,
                 "Native controller received another world or actor set")
        control = self.native["control"]
        subject = actors["subject"]
        subject.apply_control(self.carla.VehicleControl(
            throttle=float(control["subject_throttle"]) if index < int(control["approach_frames"]) else 0.0,
            brake=0.0 if index < int(control["approach_frames"]) else 1.0))
        entrant = actors["entrant"]
        moving = self.entrant_mode == "about_to_enter" and index >= int(control["entrant_start_frame"])
        entrant.apply_control(self.carla.VehicleControl(
            throttle=float(control["entrant_throttle"]) if moving else 0.0,
            brake=0.0 if moving else 1.0))
        walking = self.loading_mode == "active" and index < int(control["loading_frames"])
        passenger = actors["passenger"]
        passenger.apply_control(self.carla.WalkerControl(
            direction=self.carla.Vector3D(*control.get("passenger_direction", [1, 0, 0])),
            speed=float(control["passenger_speed_mps"]) if walking else 0.0))

    def observer(self, snapshot, actors):
        _require(actors == self.actors and self.site is not None,
                 "Native observer received another actor set")
        subject, entrant, passenger = (actors[k] for k in ("subject", "entrant", "passenger"))
        sl = subject.get_transform().location
        el = entrant.get_transform().location
        pl = passenger.get_transform().location
        sv = subject.get_velocity()
        ev = entrant.get_velocity()
        pv = passenger.get_velocity()
        distance = math.hypot(pl.x - sl.x, pl.y - sl.y)
        entry_distance = math.hypot(el.x - self.site["stand_waypoint"][0],
                                    el.y - self.site["stand_waypoint"][1])
        entrant_speed = math.sqrt(ev.x * ev.x + ev.y * ev.y + ev.z * ev.z)
        passenger_speed = math.sqrt(pv.x * pv.x + pv.y * pv.y + pv.z * pv.z)
        bounds = self.native["observation"]
        near_entry = entry_distance <= float(bounds["entry_range_m"])
        readback = {
            "passenger_loading_active": (distance <= float(bounds["loading_radius_m"]) and
                                         passenger_speed > float(bounds["motion_epsilon_mps"])),
            "entrant_waiting": near_entry and entrant_speed <= float(bounds["motion_epsilon_mps"]),
            "entrant_about_to_enter": near_entry and entrant_speed > float(bounds["motion_epsilon_mps"]),
            "access_obstructed": _inside_polygon([sl.x, sl.y], self.native["access_polygon"]) and near_entry,
        }
        participants = [{"actor_id": actor.id, "blueprint": actor.type_id,
                         "position_m": [float(actor.get_transform().location.x),
                                        float(actor.get_transform().location.y),
                                        float(actor.get_transform().location.z)]}
                        for actor in (subject, entrant, passenger)]
        body_vertices = subject.bounding_box.get_world_vertices(subject.get_transform())
        self.frames.append({"frame": int(snapshot.frame),
                            "time_s": float(snapshot.timestamp.elapsed_seconds),
                            "participants": participants,
                            "rgb_sensors": [{"actor_id": sensor.id, "blueprint": sensor.type_id}
                                            for sensor in self.sensors.values()],
                            "readback": readback,
                            "body_vertices_m": [[float(v.x), float(v.y), float(v.z)]
                                                for v in body_vertices],
                            "ego_velocity_mps": [float(sv.x), float(sv.y), float(sv.z)]})
        return readback

    def finish_cameras(self):
        expected = [(row["frame"], row["time_s"]) for row in self.frames]
        _require(len(expected) == 900, "original observer lost frames")
        deadline = time.monotonic() + 45
        while any(len(self.camera_frames[name]) < 900 for name in VIEWS):
            _require(not self.camera_errors, "original RGB callback failed: " +
                     "; ".join(self.camera_errors))
            _require(time.monotonic() < deadline, "original RGB callbacks timed out")
            time.sleep(.01)
        for name in VIEWS:
            frames = self.camera_frames[name]
            _require(len(frames) == 900 and all(
                frame == target and abs(time_s - stamp) <= 1e-4
                for (frame, time_s), (target, stamp) in zip(frames, expected)),
                "original RGB frame/time join differs: " + name)
            self.encoders[name].finish()
            self.finished_encoders.add(name)
            _require((self.root / (name + ".mkv")).is_file() and
                     (self.root / (name + ".mkv")).stat().st_size > 0,
                     "original RGB file missing: " + name)

    def export_converter_sources(self, output_dir, constructed_case, attempt_source):
        root = Path(output_dir)
        _require(root == self.root and len(self.frames) == 900 and
                 attempt_source["first_frame"] == self.frames[0]["frame"],
                 "original converter export differs from captured run")
        road = root / "road.xodr"
        _require(not road.exists(), "refusing to overwrite original road")
        road.write_text(self.mapping.to_opendrive())
        _require(road.stat().st_size > 0, "Native OpenDRIVE map empty")
        crosswalks = self.mapping.get_crosswalks()
        _json(root / "capture/native_map_facts.json", {
            "map": self.mapping.name, "junctions": [],
            "crosswalk_vertices_m": [[float(p.x), float(p.y), float(p.z)] for p in crosswalks],
            "crosswalk_inventory_scope": "Native Map.get_crosswalks original readback; junction inventory pending"})
        _require(hasattr(self.client, "get_server_version"), "Native server version source missing")
        info = root / "capture/recorder_info.txt"
        _require(not info.exists(), "refusing to overwrite original recorder info")
        info.write_text("original_live_run\nserver_version=" + str(self.client.get_server_version()) +
                        "\nmap=" + self.mapping.name + "\nframes=900\n")
        trace = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
        actor_rows = json.loads((root / "actor-rows.json").read_text())
        _require(len(trace) == len(actor_rows) == 900, "original trace/actor rows incomplete")
        evidence, native_frames = [], []
        for index, (frame, motion, actor) in enumerate(zip(self.frames, trace, actor_rows)):
            number, stamp = frame["frame"], frame["time_s"]
            _require(motion["frame"] == actor["frame"] == number and
                     abs(float(motion["time_s"]) - stamp) <= 1e-4 and
                     abs(float(actor["time_s"]) - stamp) <= 1e-4,
                     "original converter frame/time join differs")
            observation = {"frame": number, "time_s": stamp,
                           "participants": frame["participants"],
                           "rgb_sensors": frame["rgb_sensors"],
                           "map_context": {"declared_public_way_road_ids": [], "core_assumptions": []},
                           "devices": [], "relations": [],
                           "world_settings": {"no_rendering_mode": bool(self.world.get_settings().no_rendering_mode)}}
            _require(len(observation["rgb_sensors"]) == 4, "original RGB inventory incomplete")
            graph_rel = f"graphs/base/{number:08d}.adapter.json"
            graph = {"format": "native-adapter-graph-v1", "multigraph": False,
                     "metadata": {"frame": number, "observed_evidence": observation},
                     "nodes": [{"id": "ego", "attributes": {
                         "entity_id": attempt_source["subject_id"], "sem_class": "ego",
                         "vertex": motion["position_m"],
                         "original_observation": {
                             "actor_id": attempt_source["subject_id"],
                             "blueprint": self.actors["subject"].type_id,
                             "position_m": motion["position_m"],
                             "velocity_mps": frame["ego_velocity_mps"],
                             "speed_mps": actor["subject_speed_mps"],
                             "heading_deg": actor["heading_deg"],
                             "body_vertices_m": frame["body_vertices_m"]}}}], "edges": []}
            _json(root / "capture/native" / graph_rel, graph)
            native_frames.append({"frame": number, "simulation_time": stamp,
                                  "adapter_graph": graph_rel, "nodes": 1, "edges": 0,
                                  "base": None, "abstract": None,
                                  "capture_seconds": 0.0, "extraction_seconds": 0.0})
            evidence.append({"actor_id": attempt_source["subject_id"],
                             "original_frame": number, "replay_frame": number,
                             "recording_time_s": stamp, "replay_simulation_time_s": stamp,
                             "original_observations": observation,
                             "ego": graph["nodes"][0]["attributes"]["original_observation"],
                             "world": {"road_projection": {}}, "weather": {},
                             "timing": {"observation_seconds": 0.0,
                                        "graph_capture_seconds": 0.0,
                                        "graph_extraction_seconds": 0.0},
                             "visibility": None})
        _lines(root / "capture/evidence.jsonl", evidence)
        _lines(root / "capture/native/frames.jsonl", native_frames)
        _json(root / "capture/manifest.json", {
            "acquisition": "original_live_run", "diagnostic_fixture": False,
            "extraction_confirmed": True, "frames": 900,
            "complete_driving_lanes": False, "observation_contract_version": 2,
            "required_observations": [],
            "sources": {"road.xodr": _sha(road), "trace.jsonl": _sha(root / "trace.jsonl")},
            "native_map_facts": {"path": "native_map_facts.json",
                                 "sha256": _sha(root / "capture/native_map_facts.json")}})


def open_session(host, port, config, **kwargs):
    return Session(host, port, config, **kwargs)

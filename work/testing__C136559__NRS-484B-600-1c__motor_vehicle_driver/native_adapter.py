"""Source-bound CARLA bridge for original posted-speed attempts.

CARLA is imported only by create_adapter. All Native geometry comes from the
independently reviewed, hash-bound site packet. The bridge observes actual
motion and pixels; it does not assert physical or legal acceptance.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import queue
import subprocess
from pathlib import Path

from PIL import Image

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def native_plan(site: dict, map_opendrive: str) -> dict:
    native = site.get("native")
    if not isinstance(native, dict):
        raise ValueError("reviewed Native geometry packet required")
    digest = hashlib.sha256(map_opendrive.encode()).hexdigest()
    if native.get("map_opendrive_sha256") != digest:
        raise ValueError("reviewed OpenDRIVE map readback differs")
    if not native.get("vehicle_blueprint_id") or not native.get("spawn"):
        raise ValueError("reviewed vehicle blueprint and spawn required")
    poses = native.get("camera_poses")
    if not isinstance(poses, dict) or set(poses) != set(VIEWS):
        raise ValueError("four reviewed original camera poses required")
    for pose in [native["spawn"], *poses.values()]:
        if not isinstance(pose, dict) or any(type(pose.get(k)) not in (int, float) or
                                             not math.isfinite(pose[k])
                                             for k in ("x", "y", "z", "pitch", "yaw", "roll")):
            raise ValueError("finite reviewed Native pose required")
    segments = native.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValueError("reviewed route segment stations required")
    for item in segments:
        if not isinstance(item, dict) or not isinstance(item.get("road_id"), int) or \
                not item.get("segment_id") or type(item.get("on_highway")) is not bool or \
                type(item.get("s_start")) not in (int, float) or \
                type(item.get("s_end")) not in (int, float) or \
                not 0 <= item["s_start"] < item["s_end"]:
            raise ValueError("reviewed route segment definition invalid")
    return native


def route_readback(waypoint, site: dict, native: dict) -> dict:
    lane = str(waypoint.lane_id)
    directions = [name for name, reviewed in site["travel_lanes"].items()
                  if str(reviewed) == lane]
    if len(directions) != 1:
        raise ValueError("actual Native lane lacks reviewed direction")
    segments = [item for item in native["segments"]
                if item["road_id"] == waypoint.road_id and
                item["s_start"] <= waypoint.s < item["s_end"]]
    if len(segments) != 1:
        raise ValueError("actual Native station lacks unique reviewed highway segment")
    item = segments[0]
    return {"road_id": str(waypoint.road_id), "segment_id": item["segment_id"],
            "direction": directions[0], "on_highway": item["on_highway"]}


def pose(carla, item: dict):
    return carla.Transform(carla.Location(x=item["x"], y=item["y"], z=item["z"]),
                           carla.Rotation(pitch=item["pitch"], yaw=item["yaw"], roll=item["roll"]))


class OriginalAdapter:
    def __init__(self, config: dict, host: str, port: int, output: Path, carla, client=None):
        self.config, self.carla = config, carla
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.client = client or carla.Client(host, int(port))
        self.client.set_timeout(30.0)
        self.world = self.client.get_world()
        self.original_settings = None
        self.site = None
        self.native = None
        self.sensors = []
        self.encoders = {}
        self.encoder_logs = {}
        self.queues = {}
        self.first_elapsed = None
        self.index = 0
        self.media_closed = False

    def setup(self, config: dict, site: dict) -> None:
        self.native = native_plan(site, self.world.get_map().to_opendrive())
        self.site = site
        self.original_settings = self.world.get_settings()
        settings = self.world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        self.world.apply_settings(settings)
        readback = self.world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - .05) > 1e-6:
            raise ValueError("Native 20 Hz world readback failed")

    def spawn_ego(self, lane_id: str, config: dict):
        blueprint = self.world.get_blueprint_library().find(self.native["vehicle_blueprint_id"])
        if blueprint is None or not blueprint.id.startswith("vehicle."):
            raise ValueError("reviewed motor-vehicle blueprint unavailable")
        ego = self.world.try_spawn_actor(blueprint, pose(self.carla, self.native["spawn"]))
        if ego is None:
            raise ValueError("reviewed Native ego spawn obstructed")
        waypoint = self.world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
        if waypoint is None or str(waypoint.lane_id) != str(lane_id):
            ego.destroy()
            raise ValueError("reviewed spawn lane readback differs")
        return ego

    def attach_cameras(self, ego, cameras: list) -> dict:
        if self.sensors or self.encoders:
            raise ValueError("original cameras already attached")
        sensors = {}
        try:
            for spec in cameras:
                name = spec["name"]
                if name not in VIEWS or name in sensors:
                    raise ValueError("unexpected original camera")
                blueprint = self.world.get_blueprint_library().find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(spec["width"]))
                blueprint.set_attribute("image_size_y", str(spec["height"]))
                blueprint.set_attribute("fov", str(spec["fov_deg"]))
                blueprint.set_attribute("sensor_tick", "0.05")
                sensor = self.world.spawn_actor(blueprint,
                                                pose(self.carla, self.native["camera_poses"][name]),
                                                attach_to=ego)
                stream = queue.Queue(maxsize=8)
                sensor.listen(lambda image, target=stream: target.put(image, timeout=5))
                self.queues[name] = stream
                self.sensors.append(sensor)
                sensors[name] = sensor
                self._open_encoder(name)
            if set(sensors) != set(VIEWS):
                raise ValueError("original four-view camera set incomplete")
            self._open_encoder("raw")
            return sensors
        except Exception:
            for sensor in reversed(self.sensors):
                sensor.stop()
                sensor.destroy()
            self.sensors.clear()
            self._finish_encoders()
            raise

    def _open_encoder(self, name: str) -> None:
        output = self.output / (name + ".mkv")
        if output.exists():
            raise ValueError("original media destination already exists")
        log = (self.output / ("encoder-" + name + ".log")).open("wb")
        command = ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                   "-f", "image2pipe", "-framerate", "20", "-vcodec", "png",
                   "-i", "pipe:0", "-an", "-c:v", "ffv1", "-pix_fmt", "yuv420p",
                   str(output)]
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                   stderr=log)
        self.encoders[name] = process
        self.encoder_logs[name] = log

    def apply_control(self, ego, throttle: float, brake: float) -> None:
        waypoint = self.world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
        if waypoint is None:
            raise ValueError("ego left reviewed roadway")
        successors = waypoint.next(8.0)
        if not successors:
            raise ValueError("reviewed route ends before capture")
        target = successors[0].transform.location
        current = ego.get_transform()
        dx, dy = target.x - current.location.x, target.y - current.location.y
        wanted = math.degrees(math.atan2(dy, dx))
        error = (wanted - current.rotation.yaw + 180) % 360 - 180
        steer = max(-1.0, min(1.0, error / 35.0))
        ego.apply_control(self.carla.VehicleControl(throttle=float(throttle),
                                                    brake=float(brake), steer=steer))

    def tick_and_read(self, ego, cameras: dict) -> dict:
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native frame snapshot differs")
        if self.first_elapsed is None:
            self.first_elapsed = snapshot.timestamp.elapsed_seconds
        time_s = snapshot.timestamp.elapsed_seconds - self.first_elapsed
        waypoint = self.world.get_map().get_waypoint(ego.get_location(), project_to_road=False)
        if waypoint is None:
            raise ValueError("original ego roadway readback missing")
        route = route_readback(waypoint, self.site, self.native)
        pixels = {}
        for name in VIEWS:
            try:
                image = self.queues[name].get(timeout=15)
            except queue.Empty as error:
                raise ValueError("original camera frame missing: " + name) from error
            if image.frame != frame:
                raise ValueError("original camera frame join differs: " + name)
            converted = Image.frombytes("RGBA", (image.width, image.height),
                                        bytes(image.raw_data), "raw", "BGRA").convert("RGB")
            memory = io.BytesIO()
            converted.save(memory, format="PNG")
            pixels[name] = memory.getvalue()
            self.encoders[name].stdin.write(pixels[name])
        self.encoders["raw"].stdin.write(pixels["overview"])
        velocity = ego.get_velocity()
        speed = math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2)
        location = ego.get_location()
        trace = {"frame": frame, "time_s": time_s, "position":
                 {"x": location.x, "y": location.y, "z": location.z},
                 "speed_mps": speed, "road_id": route["road_id"],
                 "lane_id": str(waypoint.lane_id)}
        row = {"frame": frame, "time_s": time_s, "speed_mps": speed,
               "camera_png": pixels, "trace": trace,
               "video_frame": {"carla_frame": frame, "time_s": time_s,
                               "video_frame": self.index},
               "operating": ego.is_alive}
        row.update(route)
        self.index += 1
        return row

    def _finish_encoders(self) -> bool:
        if self.media_closed:
            return True
        passed = True
        for name, process in self.encoders.items():
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            if process.wait(timeout=90) != 0:
                passed = False
            self.encoder_logs[name].close()
        self.media_closed = True
        return passed

    def finalize_media(self, output: Path, views: tuple, mapping: tuple) -> dict:
        if tuple(views) != VIEWS or len(mapping) != 900 or self.index != 900:
            raise ValueError("original media frame map incomplete")
        if not self._finish_encoders():
            raise ValueError("original FFV1 encoder failed")
        media = {name: self.output / (name + ".mkv") for name in (*VIEWS, "raw")}
        if any(not path.is_file() or path.stat().st_size == 0 for path in media.values()):
            raise ValueError("original FFV1 stream missing")
        return media

    def destroy(self, actor) -> None:
        actor.destroy()

    def close(self) -> bool:
        passed = True
        for sensor in reversed(self.sensors):
            try:
                sensor.stop()
                sensor.destroy()
            except Exception:
                passed = False
        self.sensors.clear()
        try:
            passed = self._finish_encoders() and passed
        except Exception:
            passed = False
        if self.original_settings is not None:
            self.world.apply_settings(self.original_settings)
            readback = self.world.get_settings()
            passed = passed and readback.synchronous_mode == self.original_settings.synchronous_mode and \
                readback.fixed_delta_seconds == self.original_settings.fixed_delta_seconds
        return passed


def create_adapter(config: dict, host: str, port: int, output: Path):
    import carla
    return OriginalAdapter(config, host, port, output, carla)

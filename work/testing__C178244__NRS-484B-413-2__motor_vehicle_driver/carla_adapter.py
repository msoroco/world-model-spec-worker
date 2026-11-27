"""Lazy CARLA session for source-gated C178244 turn-signal capture.

Original map, vehicle, speed and four camera mounts come from the reviewed site
packet. The session owns and restores every world/actor/sensor resource it uses.
"""
from __future__ import annotations

import io
import math
import queue

from PIL import Image

from native_capture_contract import CAMERAS, DIMENSIONS, STEP_S


def _clip(value: float, low: float, high: float) -> float:
    return min(high, max(low, value))


class Session:
    def __init__(self, host: str, port: int, config: dict):
        self.host, self.port, self.config = host, int(port), config
        self.site = config["site"]
        self.carla = None
        self.client = None
        self.world = None
        self.original_settings = None
        self.original_weather = None
        self.ego = None
        self.sensors = {}
        self.camera_queues = {}
        self._requested_signal = False
        self.pipeline_capture = None
        self.restoration_verified = False

    def __enter__(self):
        import carla
        self.carla = carla
        try:
            client = carla.Client(self.host, self.port)
            client.set_timeout(15.0)
            self.client = client
            self.world = client.get_world()
            if self.read_map_name() != self.site["map_name"]:
                raise ValueError("reviewed map differs before Native mutation")
            self.original_settings = self.world.get_settings()
            self.original_weather = self.world.get_weather()
            settings = self.world.get_settings()
            settings.synchronous_mode = True
            settings.fixed_delta_seconds = STEP_S
            self.world.apply_settings(settings)
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        errors = []
        if self.pipeline_capture is not None:
            try:
                self.close_pipeline_capture(confirmed=False)
            except Exception as error:
                errors.append(error)
        for sensor in self.sensors.values():
            try:
                sensor.stop()
            except Exception as error:
                errors.append(error)
            try:
                sensor.destroy()
            except Exception as error:
                errors.append(error)
        self.sensors.clear()
        if self.ego is not None:
            try:
                self.ego.destroy()
            except Exception as error:
                errors.append(error)
            self.ego = None
        if self.world is not None:
            if self.original_weather is not None:
                try:
                    self.world.set_weather(self.original_weather)
                except Exception as error:
                    errors.append(error)
            if self.original_settings is not None:
                try:
                    self.world.apply_settings(self.original_settings)
                except Exception as error:
                    errors.append(error)
            if not errors and self.original_settings is not None and self.original_weather is not None:
                try:
                    restored_settings = self.world.get_settings()
                    restored_weather = self.world.get_weather()
                    self.restoration_verified = (
                        restored_settings.synchronous_mode == self.original_settings.synchronous_mode
                        and restored_settings.fixed_delta_seconds == self.original_settings.fixed_delta_seconds
                        and all(abs(getattr(restored_weather, key) -
                                    getattr(self.original_weather, key)) <= .01 for key in
                                ("cloudiness", "precipitation", "sun_altitude_angle")))
                    if not self.restoration_verified:
                        errors.append(ValueError("original world settings or weather not restored"))
                except Exception as error:
                    errors.append(error)
        if errors and exc_type is None:
            raise RuntimeError("Native resource restoration failed") from errors[0]
        return False

    def start_pipeline_capture(self, output, case_id: str) -> None:
        if self.ego is None or self.pipeline_capture is not None:
            raise ValueError("original ego or converter capture state missing")
        from pipeline_capture import PipelineCapture
        self.pipeline_capture = PipelineCapture(self.client, self.ego, output, case_id)

    def capture_pipeline_tick(self, frame: int, time_s: float) -> None:
        if self.pipeline_capture is None:
            raise ValueError("original converter capture was not started")
        self.pipeline_capture.capture(frame, time_s)

    def close_pipeline_capture(self, *, confirmed: bool = True) -> None:
        if self.pipeline_capture is not None:
            capture = self.pipeline_capture
            self.pipeline_capture = None
            capture.close(confirmed=confirmed)

    def read_map_name(self) -> str:
        return self.world.get_map().name

    def spawn_ego(self, blueprint_id: str, start: list[float]) -> dict:
        if self.ego is not None:
            raise ValueError("ego actor already spawned")
        blueprint = self.world.get_blueprint_library().find(blueprint_id)
        if blueprint is None or blueprint.id != blueprint_id:
            raise ValueError("reviewed ego blueprint unavailable")
        turn = self.site["turn_vertex_xyz"]
        yaw = math.degrees(math.atan2(turn[1] - start[1], turn[0] - start[0]))
        transform = self.carla.Transform(
            self.carla.Location(x=start[0], y=start[1], z=start[2]),
            self.carla.Rotation(yaw=yaw))
        actor = self.world.spawn_actor(blueprint, transform)
        if actor is None:
            raise ValueError("reviewed ego spawn failed")
        self.ego = actor
        if actor.type_id != blueprint_id or not actor.is_alive:
            raise ValueError("spawned ego blueprint readback differs")
        location = actor.get_transform().location
        if location.distance(transform.location) > 1.0:
            raise ValueError("spawned ego position readback differs")
        for name in CAMERAS:
            rig = self.site["camera_rigs"][name]
            bp = self.world.get_blueprint_library().find("sensor.camera.rgb")
            if bp is None:
                raise ValueError("original camera blueprint unavailable")
            width, height = DIMENSIONS[name]
            bp.set_attribute("image_size_x", str(width))
            bp.set_attribute("image_size_y", str(height))
            bp.set_attribute("sensor_tick", str(STEP_S))
            x, y, z = rig["relative_xyz"]
            heading, pitch, roll = rig["relative_ypr_deg"]
            pose = self.carla.Transform(self.carla.Location(x=x, y=y, z=z),
                                        self.carla.Rotation(yaw=heading, pitch=pitch, roll=roll))
            sensor = self.world.spawn_actor(bp, pose, attach_to=actor)
            if sensor is None:
                raise ValueError("original camera spawn failed: " + name)
            self.sensors[name] = sensor
            target = self.camera_queues[name] = queue.Queue(maxsize=2)
            sensor.listen(lambda image, q=target: q.put_nowait(image))
        return {"actor_id": actor.id}

    def set_weather(self, name: str) -> None:
        presets = {"clear": self.carla.WeatherParameters.ClearNoon,
                   "rain": self.carla.WeatherParameters.HardRainNoon}
        if name not in presets:
            raise ValueError("unknown reviewed weather request")
        self.world.set_weather(presets[name])
        self._weather_name = name

    def read_weather(self) -> str:
        presets = {"clear": self.carla.WeatherParameters.ClearNoon,
                   "rain": self.carla.WeatherParameters.HardRainNoon}
        actual = self.world.get_weather()
        expected = presets.get(getattr(self, "_weather_name", None))
        if expected is None or any(abs(getattr(actual, key) - getattr(expected, key)) > .01
                                   for key in ("cloudiness", "precipitation", "sun_altitude_angle")):
            raise ValueError("original weather differs from requested preset")
        return self._weather_name

    def read_ego_state(self) -> dict:
        transform = self.ego.get_transform()
        velocity = self.ego.get_velocity()
        vertices = self.ego.bounding_box.get_world_vertices(transform)
        if len(vertices) != 8:
            raise ValueError("original ego bounding box vertices missing")
        return {"actor_id": self.ego.id, "blueprint_id": self.ego.type_id,
                "x_m": transform.location.x, "y_m": transform.location.y,
                "heading_deg": transform.rotation.yaw,
                "speed_m_s": math.sqrt(velocity.x ** 2 + velocity.y ** 2 + velocity.z ** 2),
                "body_vertices_m": [[point.x, point.y] for point in vertices]}

    def command_drive(self, target: list[float]) -> None:
        state = self.read_ego_state()
        wanted = math.degrees(math.atan2(target[1] - state["y_m"], target[0] - state["x_m"]))
        difference = (wanted - state["heading_deg"] + 180) % 360 - 180
        goal_speed = float(self.site["drive_speed_m_s"])
        speed = state["speed_m_s"]
        control = self.carla.VehicleControl(
            steer=_clip(difference / 50.0, -0.75, 0.75),
            throttle=_clip((goal_speed - speed) * .25, 0, .55),
            brake=_clip((speed - goal_speed) * .3, 0, .6))
        self.ego.apply_control(control)

    def request_left_signal(self, active: bool) -> None:
        lights = self.ego.get_light_state()
        bit = self.carla.VehicleLightState.LeftBlinker
        requested = (lights | bit) if active else (lights & ~bit)
        self.ego.set_light_state(self.carla.VehicleLightState(requested))
        self._requested_signal = active

    def read_left_signal(self) -> bool:
        return bool(self.ego.get_light_state() & self.carla.VehicleLightState.LeftBlinker)

    def tick(self) -> dict:
        frame = self.world.tick()
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise ValueError("Native tick and snapshot frame differ")
        return {"frame": frame, "time_s": snapshot.timestamp.elapsed_seconds}

    def read_camera(self, name: str, frame: int) -> dict:
        if name not in self.camera_queues:
            raise ValueError("unknown original camera")
        image = self.camera_queues[name].get(timeout=15)
        if image.frame != frame or (image.width, image.height) != DIMENSIONS[name]:
            raise ValueError("original camera frame or dimensions differ")
        rgb = Image.frombytes("RGBA", (image.width, image.height),
                              bytes(image.raw_data), "raw", "BGRA").convert("RGB")
        stream = io.BytesIO()
        rgb.save(stream, format="PNG")
        return {"frame": image.frame, "png_bytes": stream.getvalue()}


def open_session(host: str, port: int, config: dict) -> Session:
    return Session(host, port, config)

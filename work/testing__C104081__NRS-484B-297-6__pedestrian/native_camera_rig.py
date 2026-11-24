"""Own four surveyed CARLA RGB camera actors and synchronize original images.

Camera poses must come from the hashed original site survey. This module is
CARLA lazy: CPU fakes exercise ownership and frame joins without a simulator.
"""
from __future__ import annotations

import math
from queue import Empty, Queue
from types import SimpleNamespace

from native_camera_capture import CAMERAS, NativeCameraRecorder, PROFILE
from native_construction import load_site_survey


class NativeCameraRig:
    def __init__(self, world, carla, survey_path, survey_sha256, output, *,
                 dimensions=None, timeout_s=3.0):
        survey = load_site_survey(survey_path, survey_sha256)
        views = survey.get("camera_views")
        if not isinstance(views, dict) or set(views) != set(CAMERAS):
            raise ValueError("four original surveyed camera views required")
        if not isinstance(timeout_s, (int, float)) or not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("positive camera callback timeout required")
        self.dimensions = dict(PROFILE if dimensions is None else dimensions)
        if set(self.dimensions) != set(CAMERAS):
            raise ValueError("four exact camera dimensions required")
        self.timeout_s = timeout_s
        self.sensors = {}
        self.queues = {name: Queue(maxsize=4) for name in CAMERAS}
        self.closed = False
        self.recorder = None
        transform = survey["local_to_world"]
        yaw = math.radians(transform["yaw_degrees"])
        try:
            library = world.get_blueprint_library()
            for name in CAMERAS:
                view = views[name]
                if not isinstance(view, dict) or set(view) != {"x", "y", "z", "yaw", "pitch", "roll"}:
                    raise ValueError(f"surveyed camera pose incomplete: {name}")
                if not all(type(value) in (int, float) and math.isfinite(value)
                           for value in view.values()):
                    raise ValueError(f"surveyed camera pose nonfinite: {name}")
                width, height = self.dimensions[name]
                if type(width) is not int or type(height) is not int or width < 1 or height < 1:
                    raise ValueError("invalid original camera dimensions")
                blueprint = library.find("sensor.camera.rgb")
                blueprint.set_attribute("image_size_x", str(width))
                blueprint.set_attribute("image_size_y", str(height))
                blueprint.set_attribute("fov", "90")
                blueprint.set_attribute("sensor_tick", "0.05")
                x = transform["x"] + view["x"] * math.cos(yaw) - view["y"] * math.sin(yaw)
                y = transform["y"] + view["x"] * math.sin(yaw) + view["y"] * math.cos(yaw)
                pose = carla.Transform(
                    carla.Location(x=x, y=y, z=view["z"]),
                    carla.Rotation(yaw=transform["yaw_degrees"] + view["yaw"],
                                   pitch=view["pitch"], roll=view["roll"]))
                sensor = world.spawn_actor(blueprint, pose)
                self.sensors[name] = sensor
                queue = self.queues[name]
                queue_sensor_id = sensor.id

                def on_image(image, *, target=queue, sensor_id=queue_sensor_id):
                    if target.full():
                        return
                    target.put_nowait((sensor_id, image))

                sensor.listen(on_image)
            self.recorder = NativeCameraRecorder(output, self.sensors,
                                                 dimensions=self.dimensions)
        except BaseException:
            self.close()
            raise

    def sync(self, frame: int) -> dict:
        """Read one image from each actor at exactly this world frame."""
        if self.closed or type(frame) is not int:
            raise ValueError("original camera rig closed or invalid frame")
        images = {}
        for name in CAMERAS:
            try:
                sensor_id, image = self.queues[name].get(timeout=self.timeout_s)
            except Empty as exc:
                raise ValueError(f"missing original camera callback: {name}") from exc
            if sensor_id != self.sensors[name].id or getattr(image, "frame", None) != frame:
                raise ValueError(f"stale or mismatched original camera callback: {name}")
            images[name] = SimpleNamespace(frame=image.frame, sensor_id=sensor_id,
                                           width=image.width, height=image.height,
                                           raw_data=image.raw_data)
        return self.recorder(frame, images)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.recorder is not None:
            self.recorder.abort()
        errors = []
        for name in reversed(tuple(self.sensors)):
            sensor = self.sensors[name]
            try:
                sensor.stop()
                sensor.destroy()
            except BaseException as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise RuntimeError("camera actor cleanup failed: " + "; ".join(errors))

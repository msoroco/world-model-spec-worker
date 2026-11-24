"""Four original CARLA camera archives for a parked-headlamp Native attempt.

Sensors are caller-owned. This adapter owns the listeners and lossless archives;
actual beam emission and physical aim require later original-image review.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from queue import Empty, Queue
import zipfile

from PIL import Image

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
PROFILE_DIMENSIONS = {
    "overview": (1920, 1080),
    "approach": (1280, 720),
    "reference_corner": (1280, 720),
    "driver_reference": (1280, 720),
}


class CameraRecorder:
    def __init__(self, sensors: dict, output: Path, *, timeout_seconds: float = 5.0,
                 dimensions: dict | None = None):
        if set(sensors) != set(VIEWS) or timeout_seconds <= 0:
            raise ValueError("four sensors and positive timeout required")
        dimensions = PROFILE_DIMENSIONS if dimensions is None else dimensions
        if set(dimensions) != set(VIEWS) or any(
                not isinstance(dimensions[view], (tuple, list)) or
                len(dimensions[view]) != 2 or
                any(type(size) is not int or size <= 0 for size in dimensions[view])
                for view in VIEWS):
            raise ValueError("four positive camera dimensions required")
        self.sensors = sensors
        self.output = Path(output)
        self.timeout_seconds = timeout_seconds
        self.dimensions = {view: tuple(dimensions[view]) for view in VIEWS}
        self.queues = {view: Queue() for view in VIEWS}
        self.listening = []
        self.archives = {}
        self.frames = 0
        self.closed = False

    def start(self):
        if self.listening or self.closed:
            raise ValueError("camera recorder already started or closed")
        self.output.mkdir(parents=True, exist_ok=True)
        if any((self.output / (view + ".zip")).exists() for view in VIEWS):
            raise ValueError("original camera archive already exists")
        try:
            for view in VIEWS:
                sensor = self.sensors[view]
                sensor.listen(lambda image, name=view: self.queues[name].put(image))
                self.listening.append(sensor)
            self.archives = {view: zipfile.ZipFile(self.output / (view + ".zip"), "w",
                             compression=zipfile.ZIP_STORED) for view in VIEWS}
        except Exception:
            self.close()
            raise

    @staticmethod
    def _png(image, expected_dimensions: tuple[int, int]) -> bytes:
        width, height = image.width, image.height
        if (type(width) is not int or type(height) is not int or
                width <= 0 or height <= 0):
            raise ValueError("original camera dimensions invalid")
        if (width, height) != expected_dimensions:
            raise ValueError("original camera dimensions differ from capture profile")
        raw = bytes(image.raw_data)
        if len(raw) != width * height * 4:
            raise ValueError("original camera BGRA byte count mismatch")
        rgb = Image.frombytes("RGBA", (width, height), raw, "raw", "BGRA").convert("RGB")
        stream = io.BytesIO()
        rgb.save(stream, format="PNG")
        return stream.getvalue()

    def __call__(self, frame: int) -> dict:
        if self.closed or len(self.archives) != 4 or type(frame) is not int:
            raise ValueError("camera recorder not started")
        encoded = {}
        for view in VIEWS:
            try:
                image = self.queues[view].get(timeout=self.timeout_seconds)
            except Empty as exc:
                raise ValueError("original camera callback missing: " + view) from exc
            if image.frame != frame:
                raise ValueError("original camera callback frame mismatch: " + view)
            encoded[view] = self._png(image, self.dimensions[view])
        for view in VIEWS:
            self.archives[view].writestr(f"{frame}.png", encoded[view])
        self.frames += 1
        return {view: frame for view in VIEWS}

    def finish(self, expected_frames: int) -> dict:
        if self.closed or self.frames != expected_frames:
            raise ValueError("original camera archive frame count incomplete")
        self.close()
        media = {}
        for view in VIEWS:
            path = self.output / (view + ".zip")
            with zipfile.ZipFile(path) as archive:
                if len(archive.namelist()) != expected_frames:
                    raise ValueError("original camera archive incomplete")
            media[view] = {"path": path.name,
                           "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                           "source_frame_count": expected_frames}
        return media

    def close(self):
        for sensor in self.listening:
            sensor.stop()
        self.listening.clear()
        for archive in self.archives.values():
            archive.close()
        self.closed = True

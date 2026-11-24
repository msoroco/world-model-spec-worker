"""CPU fake-world installation and complete four-camera frame join checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from camera_capture import install_cameras, validate_frame_map
from diagonal_motion import FRAMES, camera_plan


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, name, value):
        self.attributes[name] = value


class Library:
    def find(self, name):
        assert name == "sensor.camera.rgb"
        return Blueprint()


class Sensor:
    def listen(self, callback):
        self.callback = callback

    def stop(self):
        self.stopped = True

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.sensors = []

    def get_blueprint_library(self):
        return Library()

    def spawn_actor(self, blueprint, transform):
        assert blueprint.attributes["sensor_tick"] == "0.05"
        sensor = Sensor()
        self.sensors.append(sensor)
        return sensor


class Carla:
    @staticmethod
    def Location(*values):
        return values

    @staticmethod
    def Rotation(*values):
        return values

    @staticmethod
    def Transform(location, rotation):
        return (location, rotation)


def main():
    observed = []
    world = World()
    sensors = install_cameras(world, Carla, lambda name, image: observed.append((name, image)))
    assert len(sensors) == 4
    for name, sensor in sensors:
        sensor.callback(123)
    assert sorted(name for name, _ in observed) == sorted(x["name"] for x in camera_plan())
    rows = [{"camera": item["name"], "frame": frame, "native_frame": frame,
             "time_s": frame / 20, "width": item["width"], "height": item["height"],
             "source_path": f"capture/cameras/{item['name']}/{frame:08d}.png",
             "source_sha256": "diagnostic-source-hash"}
            for item in camera_plan() for frame in range(FRAMES)]
    report = validate_frame_map(rows)
    bad = rows[:-1]
    try:
        validate_frame_map(bad)
    except ValueError as error:
        assert "complete" in str(error)
    else:
        raise AssertionError("missing camera frame accepted")
    bad = list(rows)
    bad[-1] = dict(bad[-1], native_frame=0)
    try:
        validate_frame_map(bad)
    except ValueError as error:
        assert "join" in str(error)
    else:
        raise AssertionError("misjoined camera frame accepted")
    report.update(format="c109166-camera-cpu-proof-v1", passed=True,
                  acquisition_sha256=hashlib.sha256((HERE / "native/camera_capture.py").read_bytes()).hexdigest(),
                  negative_probes=2, simulation_started=False)
    (HERE / "camera-capture-proof.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()

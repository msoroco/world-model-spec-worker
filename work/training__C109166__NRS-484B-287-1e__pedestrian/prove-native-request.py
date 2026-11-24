"""CPU tests for the authored Native diagonal request and camera source join."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODULE = HERE / "native/native_request.py"
spec = importlib.util.spec_from_file_location("native_request", MODULE)
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def main():
    pair = native.validate_pair()
    class StubCarla:
        class Vector3D:
            def __init__(self, *xyz):
                self.xyz = xyz
        class WalkerControl:
            def __init__(self, direction, speed, jump):
                self.direction, self.speed, self.jump = direction, speed, jump
        class Location:
            def __init__(self, *xyz):
                self.xyz = xyz
        class Rotation:
            def __init__(self, *angles):
                self.angles = angles
        class Transform:
            def __init__(self, location, rotation):
                self.location, self.rotation = location, rotation
    class Walker:
        def apply_control(self, control):
            self.control = control
    class Blueprint:
        def __init__(self):
            self.attributes = {}
        def set_attribute(self, name, value):
            self.attributes[name] = value
    class Library:
        def find(self, name):
            if name != "sensor.camera.rgb":
                raise ValueError("wrong camera sensor")
            return Blueprint()
    class Sensor:
        def listen(self, callback):
            self.callback = callback
        def stop(self):
            self.stopped = True
        def destroy(self):
            self.destroyed = True
    class World:
        def __init__(self, fail_index=None):
            self.sensors = []
            self.fail_index = fail_index
        def get_blueprint_library(self):
            return Library()
        def spawn_actor(self, blueprint, transform):
            if len(self.sensors) == self.fail_index:
                return None
            sensor = Sensor()
            self.sensors.append((blueprint, transform, sensor))
            return sensor
    walker = Walker()
    native.apply_walker_control(walker, StubCarla, "controlled_2", 100)
    if not walker.control.speed > 0 or walker.control.jump:
        raise AssertionError("walker control was not applied")
    world = World()
    installed = native.install_cameras(world, StubCarla, lambda name, image: None)
    if len(installed) != 4 or any(row[0].attributes["sensor_tick"] != "0.05" for row in world.sensors):
        raise AssertionError("four 20 Hz cameras were not installed")
    failing_world = World(fail_index=2)
    try:
        native.install_cameras(failing_world, StubCarla, lambda name, image: None)
    except ValueError as exc:
        if "camera spawn failed" not in str(exc) or any(
                not sensor.stopped or not sensor.destroyed for _, _, sensor in failing_world.sensors):
            raise AssertionError("partial camera setup did not clean up") from exc
    else:
        raise AssertionError("partial camera failure was accepted")
    camera = {item["name"]: item for item in native.camera_plan()}
    rows = [{"camera": name, "frame": frame, "native_frame": frame,
             "time_s": frame / native.RATE_HZ, "width": item["width"],
             "height": item["height"], "source_path": f"{name}/{frame:06d}.png",
             "source_sha256": "1" * 64}
            for name, item in camera.items() for frame in range(native.FRAMES)]
    source = native.validate_source_frames(rows)
    failures = []
    for label, mutation in (
        ("missing_frame", lambda r: r.pop()),
        ("duplicate_frame", lambda r: r.__setitem__(-1, dict(r[0]))),
        ("wrong_native_frame", lambda r: r[-1].__setitem__("native_frame", 601)),
        ("missing_source", lambda r: r[-1].__setitem__("source_path", "")),
        ("wrong_time", lambda r: r[-1].__setitem__("time_s", -1.0)),
        ("wrong_dimensions", lambda r: r[-1].__setitem__("width", 1)),
    ):
        trial = [dict(row) for row in rows]
        mutation(trial)
        try:
            native.validate_source_frames(trial)
        except ValueError as exc:
            failures.append({"mutation": label, "error": str(exc)})
        else:
            raise AssertionError("camera mutation accepted: " + label)
    result = {"format": "c109166-287-1e-native-request-cpu-proof-v1",
              "module_sha256": hashlib.sha256(MODULE.read_bytes()).hexdigest(),
              "pair": pair, "source_frame_join": source, "rejected_mutations": failures,
              "stubbed_walker_control_applied": True,
              "stubbed_four_camera_install_passed": True,
              "stubbed_partial_install_cleanup_passed": True,
              "native_executed": False, "official_device_verified": False,
              "original_pixels_reviewed": False}
    target = HERE / "native-request-proof.json"
    target.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

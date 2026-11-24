import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("native_capture", ROOT / "native_capture.py")
native_capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_capture)
encode_spec = importlib.util.spec_from_file_location("encode_original", ROOT / "encode_original.py")
encode_original = importlib.util.module_from_spec(encode_spec)
encode_spec.loader.exec_module(encode_original)
runner_spec = importlib.util.spec_from_file_location("runner", ROOT / "runner.py")
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)
CASE = "testing__C215286__NRS-484B-113-2__motor_vehicle_driver__reverse_clear"


class Point:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class FakeActor:
    id = 4
    type_id = "vehicle.car"

    def __init__(self):
        self.frame = 0
        self.control = None
        self.destroyed = False
        self.bounding_box = self

    def get_world_vertices(self, transform):
        x = transform.location.x
        return [Point(x + dx, 1 + dy, z) for z in (0, 1)
                for dx, dy in ((0, 0), (1, 0), (1, 1), (0, 1))]

    def get_transform(self):
        x = 5 - self.frame * .005
        return type("Transform", (), {"location": Point(x, 1),
                                      "rotation": type("Rotation", (), {"yaw": 0})(),
                                      "get_forward_vector": lambda self: Point(1, 0)})()

    def apply_control(self, control):
        self.control = control

    def get_control(self):
        return self.control

    def get_velocity(self):
        return Point(-.1, 0)

    def destroy(self):
        self.destroyed = True


class FakeWorld:
    def __init__(self):
        self.actor = FakeActor()
        self.frame = 0

    def get_map(self):
        return type("Map", (), {"name": "Town", "to_opendrive": lambda self: "odr"})()

    def get_blueprint_library(self):
        return type("Library", (), {"find": lambda self, name: type("BP", (), {"id": name})()})()

    def try_spawn_actor(self, bp, transform):
        return self.actor

    def tick(self):
        self.frame += 1
        self.actor.frame = self.frame
        return self.frame

    def get_snapshot(self):
        return type("Snapshot", (), {"frame": self.frame,
                                    "timestamp": type("Time", (), {"elapsed_seconds": self.frame / 20})()})()


class FakeCarla:
    Location = lambda *xyz: xyz
    Rotation = lambda *rpy: rpy
    Transform = lambda location, rotation: (location, rotation)

    class VehicleControl:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)


def packet(root):
    from test_site_packet import site, CASE as SOURCE_CASE
    assert CASE == SOURCE_CASE
    source = root / "source.json"
    raw = json.dumps(site(), sort_keys=True).encode()
    source.write_bytes(raw)
    value = dict(site(), case_id=CASE, site_source_path=str(source),
                 site_source_sha256=hashlib.sha256(raw).hexdigest())
    path = root / "packet.json"
    path.write_text(json.dumps(value))
    return path


class NativeCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.site = packet(self.root)
        self.output = self.root / "capture"
        self.output.mkdir()

    def test_original_interval_and_source_joins(self):
        world = FakeWorld()
        result = native_capture.capture(world, FakeCarla, self.site, CASE, self.output,
                                        lambda frame: {name: {"frame": frame,
                                                              "source_sensor": name,
                                                              "bytes": b"fixture-image"}
                                                       for name in native_capture.VIEWS})
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual(result["camera_frames_per_view"]["overview"], 900)
        self.assertTrue(world.actor.destroyed)
        self.assertEqual(len((self.output / "channels/reverse-body-crosswalk.jsonl").read_text().splitlines()), 900)
        self.assertEqual(len((self.output / "video_frames.jsonl").read_text().splitlines()), 900)
        self.assertEqual(result["legal_judgment"], "unresolved")
        checked = encode_original.validate_capture(self.output, CASE)
        self.assertEqual(checked["camera_sensors"]["overview"], "overview")
        scene = {"law_id": "NRS-484B-113-2", "cell_id": "C215286",
                 "actor": "motor_vehicle_driver", "case_id": CASE,
                 "target_physical_relation": "disjoint", "fps": 20,
                 "camera_names": list(runner.VIEWS)}
        self.assertEqual(runner.check(scene)["target"], "disjoint")
        measured, target_rows, distance = runner._project(
            self.root, scene, json.loads(self.site.read_text()))
        self.assertEqual(len(measured["frames"]), 900)
        self.assertTrue(target_rows)
        self.assertGreater(distance, 0)
        self.assertEqual(len((self.root / "reverse_history.jsonl").read_text().splitlines()), 900)
        image = self.output / "cameras/overview/0000.png"
        image.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "camera bytes changed"):
            encode_original.validate_capture(self.output, CASE)

    def test_reject_changed_source_before_native_spawn(self):
        (self.root / "source.json").write_text((self.root / "source.json").read_text() + " ")
        world = FakeWorld()
        with self.assertRaisesRegex(ValueError, "hash differs"):
            native_capture.capture(world, FakeCarla, self.site, CASE, self.output, lambda frame: {})
        self.assertFalse(world.actor.destroyed)

    def test_reject_camera_frame_mismatch_and_cleanup(self):
        world = FakeWorld()
        with self.assertRaisesRegex(ValueError, "camera source/frame mismatch"):
            native_capture.capture(world, FakeCarla, self.site, CASE, self.output,
                                   lambda frame: {name: {"frame": frame + 1,
                                                         "source_sensor": name, "bytes": b"image"}
                                                  for name in native_capture.VIEWS})
        self.assertTrue(world.actor.destroyed)


if __name__ == "__main__":
    unittest.main()

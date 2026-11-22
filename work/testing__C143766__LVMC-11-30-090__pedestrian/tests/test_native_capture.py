import math
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import (CAMERA_SPECS, FourViewJoin, camera_placements,
                            FourVideoRecorder, sample_original_walker,
                            spawn_native_cameras)


class NativeCaptureTests(unittest.TestCase):
    def actor(self, *, bad_vertex=False):
        class Box:
            def get_world_vertices(self, transform):
                return [type("Vertex", (), {"x": x, "y": y,
                                             "z": math.nan if bad_vertex else z})()
                        for z in (0.0, 1.7) for x in (2.0, 2.4)
                        for y in (1.25, 1.75)]
        class Actor:
            id = 17
            bounding_box = Box()
            def get_transform(self): return object()
        return Actor()

    def snapshot(self, frame=10, time_s=.5):
        return type("Snapshot", (), {"frame": frame,
                    "timestamp": type("Timestamp", (), {"elapsed_seconds": time_s})()})()

    def images(self, frame=10):
        class Data:
            def __init__(self, size): self.size = size
            def __len__(self): return self.size
        return {name: type("Image", (), {"frame": frame, "width": width,
                        "height": height, "raw_data": Data(width*height*4)})()
                for name, (width, height) in CAMERA_SPECS.items()}

    def test_original_bbox_and_four_exact_camera_joins(self):
        sample = sample_original_walker({"case_id": "exact"}, self.actor(), self.snapshot())
        self.assertEqual(sample["body_xy_m"], [[2.0, 1.25], [2.4, 1.25],
                                              [2.4, 1.75], [2.0, 1.75]])
        join = FourViewJoin()
        receipt = join.append(sample, self.images())
        self.assertEqual(set(receipt["cameras"]), set(CAMERA_SPECS))
        next_sample = sample_original_walker({"case_id": "exact"}, self.actor(),
                                             self.snapshot(11, .55))
        self.assertEqual(join.append(next_sample, self.images(11))["frame"], 11)

    def test_missing_stale_or_invalid_camera_rejected_without_advancing(self):
        sample = sample_original_walker({"case_id": "exact"}, self.actor(), self.snapshot())
        for problem in ("missing", "stale", "size", "bytes"):
            with self.subTest(problem=problem):
                images = self.images()
                if problem == "missing": del images["trail"]
                if problem == "stale": images["trail"].frame = 9
                if problem == "size": images["trail"].width = 20
                if problem == "bytes": images["trail"].raw_data.size -= 4
                join = FourViewJoin()
                with self.assertRaises(ValueError): join.append(sample, images)
                self.assertEqual(join.append(sample, self.images())["frame"], 10)

    def test_bad_body_and_world_frame_sequence_rejected(self):
        with self.assertRaisesRegex(ValueError, "nonfinite original walker body"):
            sample_original_walker({"case_id": "exact"}, self.actor(bad_vertex=True),
                                   self.snapshot())
        join = FourViewJoin()
        sample = sample_original_walker({"case_id": "exact"}, self.actor(), self.snapshot())
        join.append(sample, self.images())
        for frame, time_s in ((12, .6), (11, .8)):
            with self.subTest(frame=frame, time_s=time_s):
                later = sample_original_walker({"case_id": "exact"}, self.actor(),
                                               self.snapshot(frame, time_s))
                with self.assertRaises(ValueError): join.append(later, self.images(frame))

    def test_four_sensor_spawns_and_partial_cleanup(self):
        import json
        scene = json.loads((ROOT/"cases/roadway_walk/scene.json").read_text())
        placements = camera_placements(scene)
        self.assertEqual(set(placements), set(CAMERA_SPECS))
        for placement in placements.values():
            self.assertTrue(all(math.isfinite(v) for v in
                                (*placement["location_xyz_m"],
                                 *placement["rotation_pitch_yaw_deg"])))
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value
        class Library:
            def find(self, name):
                if name != "sensor.camera.rgb": raise ValueError(name)
                return Blueprint()
        class Sensor:
            def __init__(self): self.destroyed = False
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self, fail_at=None):
                self.fail_at = fail_at; self.calls = []; self.sensors = []
            def get_blueprint_library(self): return Library()
            def spawn_actor(self, blueprint, transform):
                self.calls.append((blueprint.attributes, transform))
                if len(self.calls) == self.fail_at: return None
                sensor = Sensor(); self.sensors.append(sensor); return sensor
        class Carla:
            @staticmethod
            def Location(**values): return values
            @staticmethod
            def Rotation(**values): return values
            @staticmethod
            def Transform(location, rotation): return location, rotation
        world = World()
        self.assertEqual(set(spawn_native_cameras(world, scene, Carla)), set(CAMERA_SPECS))
        self.assertEqual([call[0]["image_size_x"] for call in world.calls],
                         [str(CAMERA_SPECS[name][0]) for name in CAMERA_SPECS])
        failing = World(fail_at=3)
        with self.assertRaisesRegex(ValueError, "sidewalk Native camera spawn failed"):
            spawn_native_cameras(failing, scene, Carla)
        self.assertTrue(all(sensor.destroyed for sensor in failing.sensors))

    def test_four_video_recorder_writes_joined_frames_and_closes(self):
        import json
        scene = json.loads((ROOT/"cases/roadway_walk/scene.json").read_text())
        class Blueprint:
            def set_attribute(self, key, value): pass
        class Library:
            def find(self, name): return Blueprint()
        class Sensor:
            def __init__(self): self.callback = None; self.stopped = False; self.destroyed = False
            def listen(self, callback): self.callback = callback
            def stop(self): self.stopped = True
            def destroy(self): self.destroyed = True
        class World:
            def __init__(self): self.sensors = []
            def get_blueprint_library(self): return Library()
            def spawn_actor(self, blueprint, transform):
                sensor = Sensor(); self.sensors.append(sensor); return sensor
        class Carla:
            @staticmethod
            def Location(**values): return values
            @staticmethod
            def Rotation(**values): return values
            @staticmethod
            def Transform(location, rotation): return location, rotation
        class Pipe:
            def __init__(self): self.closed = False; self.written = 0
            def write(self, data): self.written += len(data); return len(data)
            def close(self): self.closed = True
        class Process:
            def __init__(self, command, **kwargs):
                self.command = command; self.stdin = Pipe(); processes.append(self)
            def wait(self, timeout): return 0
        processes = []
        world = World()
        scratch = ROOT.parents[1]/".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as attempt:
            recorder = FourVideoRecorder(world, scene, Carla, attempt, Process)
            for sensor, image in zip(world.sensors, self.images().values()):
                sensor.callback(image)
            sample = sample_original_walker(scene, self.actor(), self.snapshot())
            self.assertEqual(recorder.append(sample)["frame"], 10)
            self.assertTrue(all(p.stdin.written > 0 for p in processes))
            recorder.close()
            self.assertTrue(all(s.stopped and s.destroyed for s in world.sensors))
            self.assertTrue(all(p.stdin.closed for p in processes))

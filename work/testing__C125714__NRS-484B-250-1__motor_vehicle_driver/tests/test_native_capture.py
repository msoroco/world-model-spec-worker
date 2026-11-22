import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture import CameraBank, reviewed_context
from native_driver import apply_other


class SourceAndCameraTests(unittest.TestCase):
    def test_reviewed_context_bound_to_live_map_and_retained_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "attempt"
            output.mkdir()
            digest = hashlib.sha256(b"map bytes").hexdigest()
            crossing = {"crossing_id": "A-B", "map_source_sha256": digest,
                        "bounds_xy_m": [-1,-1,1,1]}
            law = {"map_source": digest, "ego_highway": "A", "other_highway": "B",
                   "public_access_source": "review packet", "device_inventory_source": "review packet",
                   "driver_scope_source": "review packet", "public_access": True,
                   "human_driver": True, "devices": [], "approach_relation": "crossing",
                   "left_turn_intent": False, "left_turn_realized": False}
            source.write_text(json.dumps({"crossing": crossing, "law_context": law}))
            scene = {"reviewed_context_source": str(source),
                     "reviewed_context_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                     "crossing": crossing, "ego_highway": "A", "other_highway": "B"}
            class Map:
                def to_opendrive(self): return "map bytes"
            class World:
                def get_map(self): return Map()
            self.assertEqual(reviewed_context(scene, output, World())["crossing"], crossing)
            self.assertEqual((output / "reviewed-context.json").read_bytes(), source.read_bytes())
            output.joinpath("reviewed-context.json").unlink()
            law["devices"] = ["stop_sign"]
            source.write_text(json.dumps({"crossing": crossing, "law_context": law}))
            scene["reviewed_context_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "device exclusion"):
                reviewed_context(scene, output, World())

    def test_camera_creation_frame_join_and_cleanup(self):
        class Sensor:
            def __init__(self): self.callback = None; self.stopped = self.destroyed = False
            def listen(self, fn): self.callback = fn
            def stop(self): self.stopped = True
            def destroy(self): self.destroyed = True
        class Blueprint:
            def __init__(self): self.attributes = {}
            def set_attribute(self, key, value): self.attributes[key] = value
        class Library:
            def __init__(self): self.blueprints = []
            def find(self, name):
                self.blueprints.append(Blueprint()); return self.blueprints[-1]
        class World:
            def __init__(self):
                self.sensors = []; self.library = Library(); self.attachments = []; self.transforms = []
            def get_blueprint_library(self): return self.library
            def spawn_actor(self, bp, transform, attach_to=None):
                self.attachments.append(attach_to)
                self.transforms.append(transform)
                sensor = Sensor(); self.sensors.append(sensor); return sensor
        class Carla:
            @staticmethod
            def Location(**kwargs): return kwargs
            @staticmethod
            def Rotation(**kwargs): return kwargs
            @staticmethod
            def Transform(location, rotation): return location, rotation
        class Pipe:
            def __init__(self): self.data = b""; self.closed = False
            def write(self, data): self.data += data
            def close(self): self.closed = True
        class Encoder:
            def __init__(self): self.stdin = Pipe()
            def wait(self, timeout): return 0
        world = World(); ego = object(); encoders = []
        def start(*args, **kwargs):
            encoder = Encoder(); encoders.append(encoder); return encoder
        with tempfile.TemporaryDirectory() as directory, patch("native_capture.subprocess.Popen", side_effect=start):
            bank = CameraBank(world, ego, directory, Carla,
                              {"crossing": {"bounds_xy_m": [9,19,11,21]},
                               "ego_route_xy_m": [[5,20],[10,20],[15,20]]})
            self.assertEqual(len(world.sensors), 4)
            self.assertEqual(world.attachments, [None,None,None,ego])
            self.assertEqual(world.transforms[0][0]["x"], 10)
            self.assertEqual(world.transforms[0][0]["y"], 20)
            self.assertEqual(world.library.blueprints[0].attributes["image_size_x"], "1920")
            for sensor in world.sensors:
                sensor.callback(type("Image", (), {"frame": 41, "raw_data": b"original"})())
            bank.append(41)
            self.assertTrue(all(encoder.stdin.data == b"original" for encoder in encoders))
            bank.close()
            self.assertTrue(all(sensor.stopped and sensor.destroyed for sensor in world.sensors))
            self.assertTrue(all(encoder.stdin.closed for encoder in encoders))

    def test_other_route_actuates_steering_and_stops_at_endpoint(self):
        class Actor:
            def __init__(self): self.x = -4; self.y = 0; self.yaw = 0; self.control = None
            def get_transform(self):
                return type("Pose", (), {"location": type("Loc", (), {"x": self.x, "y": self.y})(),
                                         "rotation": type("Rot", (), {"yaw": self.yaw})()})()
            def get_velocity(self): return type("Vel", (), {"x": 0, "y": 0})()
            def apply_control(self, control): self.control = control
        class Carla:
            @staticmethod
            def VehicleControl(**kwargs): return kwargs
        actor = Actor()
        route = [[-4,0],[0,0],[4,0]]
        request = apply_other(actor, Carla, route)
        self.assertGreater(actor.control["throttle"], 0)
        self.assertEqual(request["target_index"], 1)
        actor.x = 4
        request = apply_other(actor, Carla, route, target_index=request["target_index"])
        self.assertTrue(request["arrived_request"])
        self.assertEqual(actor.control["brake"], 1)


if __name__ == "__main__": unittest.main()

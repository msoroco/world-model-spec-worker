"""CPU fake exercises exact blueprint, spawn and physical body readback."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from parking_native_driver import spawn_vehicle
from parking_scene import build
from test_source_review import fixture


class NativeDriverTests(unittest.TestCase):
    def test_spawn_calls_and_body_readback_for_six_drafts(self):
        with TemporaryDirectory() as tmp:
            packet, data = fixture(tmp)
            for activity in ("park", "stand"):
                import json
                data["context"]["activity"] = activity
                packet.write_text(json.dumps(data))
                for suffix in (activity + "_parallel_lawful",
                               activity + "_angled_lawful",
                               activity + "_parallel_reverse"):
                    scene = build(packet, tmp, suffix)
                    calls = []

                    class Vehicle:
                        bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2.25, y=1))

                        def get_transform(self):
                            return calls[-1][1]

                        def destroy(self):
                            calls.append(("destroy",))

                    vehicle = Vehicle()

                    class World:
                        def get_blueprint_library(self):
                            return SimpleNamespace(find=lambda name: name if name ==
                                                   scene["vehicle_blueprint_id"] else None)

                        def spawn_actor(self, blueprint, transform):
                            calls.append((blueprint, transform))
                            return vehicle

                    carla = SimpleNamespace(
                        Location=lambda **k: SimpleNamespace(**k),
                        Rotation=lambda **k: SimpleNamespace(**k),
                        Transform=lambda location, rotation: SimpleNamespace(location=location,
                                                                            rotation=rotation))
                    self.assertIs(spawn_vehicle(World(), scene, carla), vehicle)
                    self.assertEqual(calls[0][0], "vehicle.tesla.model3")
                    self.assertAlmostEqual(calls[0][1].location.x, scene["spawn_center_xy_m"][0])
                    self.assertEqual(len(calls), 1)

    def test_wrong_native_body_is_destroyed(self):
        with TemporaryDirectory() as tmp:
            packet, _ = fixture(tmp)
            scene = build(packet, tmp, "park_parallel_lawful")
            destroyed = []

            class Vehicle:
                bounding_box = SimpleNamespace(extent=SimpleNamespace(x=1, y=1))

                def destroy(self):
                    destroyed.append(True)

            world = SimpleNamespace(get_blueprint_library=lambda: SimpleNamespace(find=lambda name: name),
                                    spawn_actor=lambda *a: Vehicle())
            carla = SimpleNamespace(Location=lambda **k: k, Rotation=lambda **k: k,
                                    Transform=lambda location, rotation: (location, rotation))
            with self.assertRaisesRegex(ValueError, "body differs"):
                spawn_vehicle(world, scene, carla)
            self.assertEqual(destroyed, [True])


if __name__ == "__main__":
    unittest.main()

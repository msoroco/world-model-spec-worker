import copy
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagonal_crossing import advance_walker, spawn_walker, validate_site
from crossing_audit import audit_comparison, audit_history


class SiteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        sources = {}
        for name in ("map", "corner_survey", "authorization", "device_inventory", "exception_review"):
            path = Path(self.tmp.name, name + ".txt")
            path.write_text(name + " measured source")
            sources[name] = {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.packet = {"sources": sources, "coordinate_frame": "map_xy_m",
                       "corners_clockwise": [[0, 0], [10, 0], [10, 10], [0, 10]],
                       "pedestrian_route": [[0, 0], [5, 5], [10, 10]],
                       "governing_device": {"id": "ped-1", "authority_record_id": "order-1",
                                            "instruction_record_id": "order-1-diagonal",
                                            "placement_record_id": "survey-1", "governs": "pedestrian_diagonal",
                                            "diagonal_authorized": True},
                       "observed_device_ids": ["ped-1"], "exception_484b_290_review": "unresolved",
                       "walker_blueprint_id": "walker.pedestrian.0001", "spawn_z_m": 0.4}

    def test_source_and_diagonal_gate(self):
        self.assertEqual(validate_site(self.packet)["destination_xy"], (10.0, 10.0))
        for change in ({"governs": "motor_vehicle"}, {"diagonal_authorized": False}):
            packet = copy.deepcopy(self.packet)
            packet["governing_device"].update(change)
            with self.assertRaises(ValueError):
                validate_site(packet)
        packet = copy.deepcopy(self.packet)
        packet["pedestrian_route"][-1] = [10, 0]
        with self.assertRaises(ValueError):
            validate_site(packet)
        Path(self.packet["sources"]["authorization"]["path"]).write_text("altered")
        with self.assertRaises(ValueError):
            validate_site(self.packet)

    def test_spawn_and_route_controller(self):
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z
        class Actor:
            type_id = "walker.pedestrian.0001"
            def __init__(self):
                self.location = Location(0, 0, 0.4)
                self.controls = []
                self.destroyed = False
            def get_location(self): return self.location
            def apply_control(self, c): self.controls.append(c)
            def destroy(self): self.destroyed = True
        actor = Actor()
        carla = SimpleNamespace(Location=Location, Transform=lambda p: p,
                                Vector3D=lambda x, y, z: (x, y, z),
                                WalkerControl=lambda **kw: kw)
        world = SimpleNamespace(get_blueprint_library=lambda: SimpleNamespace(find=lambda n: n),
                                try_spawn_actor=lambda bp, transform: actor)
        spawned, plan = spawn_walker(world, self.packet, carla_module=carla)
        self.assertIs(spawned, actor)
        self.assertEqual(advance_walker(actor, plan, 1, 1.2, carla_module=carla), 1)
        self.assertGreater(actor.controls[-1]["speed"], 0)
        actor.location = Location(5, 5, 0.4)
        self.assertEqual(advance_walker(actor, plan, 1, 1.2, carla_module=carla), 2)
        actor.location = Location(10, 10, 0.4)
        self.assertEqual(advance_walker(actor, plan, 2, 1.2, carla_module=carla), 2)
        self.assertEqual(actor.controls[-1]["speed"], 0)

    def test_original_frame_and_comparison_audit(self):
        plan = validate_site(self.packet)
        positions = [[0, 0], [3, 3], [5, 5], [7, 7], [10, 10]]
        walker = [{"original_frame": 20+i, "walker_id": 7, "center_xy": p} for i, p in enumerate(positions)]
        devices = [{"original_frame": 20+i, "device_id": "ped-1", "source_sha256": "abc",
                    "pedestrian_governance": "diagonal", "instruction": "diagonal_walk"} for i in range(5)]
        polygon = [[2, 2], [8, 2], [8, 8], [2, 8]]
        reference = audit_history(plan, polygon, walker, devices)
        self.assertTrue(reference["all_crossing_frames_permissive"])
        changed = copy.deepcopy(devices)
        changed[2]["instruction"] = "diagonal_dont_walk"
        variant = audit_history(plan, polygon, walker, changed)
        self.assertTrue(audit_comparison(reference, variant)["comparison_verified"])
        changed[2]["pedestrian_governance"] = "vehicle"
        with self.assertRaises(ValueError):
            audit_history(plan, polygon, walker, changed)
        broken = copy.deepcopy(devices)
        broken.pop(2)
        with self.assertRaises(ValueError):
            audit_history(plan, polygon, walker, broken)
        different = copy.deepcopy(variant)
        different["crossing_frames"] = [20]
        with self.assertRaises(ValueError):
            audit_comparison(reference, different)


if __name__ == "__main__":
    unittest.main()

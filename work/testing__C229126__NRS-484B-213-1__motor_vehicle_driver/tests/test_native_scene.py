import copy
import hashlib
import importlib.util
import unittest
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "native_scene.py"
spec = importlib.util.spec_from_file_location("native_scene", MODULE)
scene = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scene)


def packet(variant):
    def actor(direction):
        return {"blueprint": "vehicle.test", "pose": [0, 0, 0, 0, 0 if direction == 1 else 180, 0],
                "route": [[0, 0, 0], [10*direction, 0, 0]], "target_speed_mps": 10,
                "source_sha256": "reviewed-actor", "direction": direction}
    return {"case_id": scene.ASSIGNMENT + "__" + variant,
            "law_id": "NRS-484B-213-1", "cell_id": "C229126",
            "actor": "motor_vehicle_driver", "reviewed": True,
            "reviewer": "independent source reviewer",
            "review_source_sha256": "reviewed-road", "map_opendrive_sha256": hashlib.sha256(b"road").hexdigest(),
            "road": {"public_highway": True, "lane_count": 2,
                     "opposite_permitted_directions": True, "undivided": True,
                     "centerline_source_sha256": "reviewed-line",
                     "forward_unit_xy": [1, 0],
                     "centerline_origin_xy": [0, 0],
                     "lanes": [{"direction": 1, "lane_id": "forward"},
                               {"direction": -1, "lane_id": "reverse"}]},
            "actors": {"ego": actor(1), "overtaken": actor(1), "oncoming": actor(-1)},
            "opaque_blocker": {"blueprint": "static.prop.wall", "pose": [2, 2, 0, 0, 0, 0],
                               "source_sha256": "reviewed-blocker", "ray_intersection_plan": "ray from ego into opposing lane"},
            "cameras": {name: {"pose": [0, 0, 4, -20, 0, 0], "width": size[0],
                               "height": size[1], "fov_deg": 90}
                        for name, size in zip(scene.CAMERAS, scene.CAMERA_SIZES)},
            "fps": 20, "duration_s": 45}


class FakeBlueprint:
    def __init__(self, name): self.name = name; self.attributes = {}
    def set_attribute(self, key, value): self.attributes[key] = value


class FakeLibrary:
    def find(self, name): return FakeBlueprint(name)


class FakeActor:
    def __init__(self, blueprint, pose): self.blueprint = blueprint; self.pose = pose; self.destroyed = False; self.stopped = False; self.control = None
    def stop(self): self.stopped = True
    def destroy(self): self.destroyed = True
    def get_location(self): return type("Point", (), {"x": 0, "y": 0})()
    def get_transform(self): return type("Pose", (), {"rotation": type("Rotation", (), {"yaw": self.pose[1]["yaw"]})()})()
    def get_velocity(self): return type("Velocity", (), {"x": 0, "y": 0, "z": 0})()
    def apply_control(self, control): self.control = control


class FakeMap:
    def to_opendrive(self): return "road"


class FakeWorld:
    def __init__(self): self.spawned = []; self.frame = 0; self.settings = type("Settings", (), {"synchronous_mode": False, "fixed_delta_seconds": None})()
    def get_map(self): return FakeMap()
    def get_settings(self): return self.settings
    def apply_settings(self, value): self.settings = value
    def get_blueprint_library(self): return FakeLibrary()
    def try_spawn_actor(self, blueprint, pose):
        actor = FakeActor(blueprint, pose)
        self.spawned.append(actor)
        return actor
    def spawn_actor(self, blueprint, pose): return self.try_spawn_actor(blueprint, pose)
    def tick(self): self.frame += 1; return self.frame


class FakeClient:
    def __init__(self): self.world = FakeWorld()
    def get_world(self): return self.world


class FakeCarla:
    @staticmethod
    def Location(**values): return values
    @staticmethod
    def Rotation(**values): return values
    @staticmethod
    def Transform(location, rotation): return (location, rotation)
    @staticmethod
    def VehicleControl(**values): return values


class NativeSceneTest(unittest.TestCase):
    def test_two_way_lane_and_oncoming_binding(self):
        data = packet("oncoming_close")
        self.assertIs(scene.validate(data, data["case_id"]), data)
        wrong = copy.deepcopy(data)
        wrong["actors"]["oncoming"]["direction"] = 1
        with self.assertRaisesRegex(ValueError, "route contradicts"):
            scene.validate(wrong, data["case_id"])

    def test_occluder_is_spawned_and_released(self):
        data = packet("occluded_left")
        client = FakeClient()
        built = scene.PassScene(client, data, data["case_id"], ".", carla_module=FakeCarla,
                                snapshot_fn=lambda client: {"saved": True},
                                restore_fn=lambda client, saved: {"restored": True},
                                bind_fn=lambda packet, root: {"map": "reviewed"})
        summary = built.begin()
        self.assertEqual(summary["actor_roles"], ["ego", "oncoming", "opaque_blocker", "overtaken"])
        self.assertEqual(len(client.world.spawned), 8)
        self.assertEqual(sum(a.blueprint.name == "static.prop.wall" for a in client.world.spawned), 1)
        release = built.close()
        self.assertTrue(release["world_restored"])
        self.assertTrue(all(actor.destroyed for actor in client.world.spawned))

    def test_occluder_missing_rejected(self):
        data = packet("occluded_left")
        del data["opaque_blocker"]
        with self.assertRaisesRegex(ValueError, "physical opaque blocker"):
            scene.validate(data, data["case_id"])

    def test_live_map_hash_mismatch_restores(self):
        data = packet("clear_free_complete")
        data["map_opendrive_sha256"] = "different"
        client = FakeClient()
        restored = []
        built = scene.PassScene(client, data, data["case_id"], ".", carla_module=FakeCarla,
                                snapshot_fn=lambda client: {"saved": True},
                                restore_fn=lambda client, saved: restored.append(True) or {"restored": True},
                                bind_fn=lambda packet, root: {"map": "reviewed"})
        with self.assertRaisesRegex(ValueError, "OpenDRIVE differs"):
            built.begin()
        self.assertEqual(restored, [True])
        self.assertFalse(client.world.spawned)

    def test_controller_uses_opposite_route_and_response(self):
        data = packet("opposite_response")
        data["actors"]["oncoming"]["route"] = [[0, 0, 0], [-10, 0, 0]]
        data["actors"]["oncoming"]["response_policy"] = {
            "start_frame": 1, "target_speed_mps": 2,
            "source_sha256": "reviewed-response"}
        client = FakeClient()
        built = scene.PassScene(client, data, data["case_id"], ".", carla_module=FakeCarla,
                                snapshot_fn=lambda client: {"saved": True},
                                restore_fn=lambda client, saved: {"restored": True},
                                bind_fn=lambda packet, root: {"map": "reviewed"})
        built.begin()
        first = built.tick(0)
        second = built.tick(1)
        self.assertEqual(first["world_frame"], 1)
        self.assertEqual(second["world_frame"], 2)
        self.assertEqual(next(c for c in second["commands"] if c["role"] == "oncoming")["target_speed_mps"], 2)
        self.assertAlmostEqual(built.actors["oncoming"].control["steer"], 0, places=5)
        built.close()


if __name__ == "__main__": unittest.main()

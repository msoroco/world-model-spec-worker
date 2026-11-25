import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_officer import read_officer_source, construct, read_command, bind_recipient, route_digest
from test_native_device import CARLA, Location, Transform

SITE = {"map_name": "TownX", "police_authority_source": "dispatch-order-7",
        "vehicle_route": [[-10, 0, 0], [10, 0, 0]]}
PACKET = {"source_kind": "original_local_officer_authority_and_gesture",
          "map_name": "TownX", "authority_source": "dispatch-order-7",
          "officer_blueprint_id": "walker.police", "gesture_asset_id": "gesture.proceed",
          "spawn_xyz": [1, 2, 0], "recipient_role": "selected_cycle_operator",
          "recipient_route_sha256": route_digest(SITE), "command": "proceed",
          "start_frame": 100, "end_frame": 120,
          "visible_camera_ids": ["front", "side"]}


class Officer:
    id = 99
    is_alive = True
    type_id = "walker.police"

    def __init__(self, pose):
        self.pose = pose
        self.destroyed = False

    def get_transform(self):
        return self.pose

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.actor = None

    def get_map(self):
        return type("Map", (), {"name": "TownX"})()

    def get_blueprint_library(self):
        return type("Library", (), {"find": lambda self, key: type("BP", (), {"id": key})()})()

    def spawn_actor(self, bp, pose):
        self.actor = Officer(pose)
        return self.actor


class TestOfficer(unittest.TestCase):
    def test_source_packet(self):
        with tempfile.TemporaryDirectory(dir=Path(".runtime-work").resolve()) as d:
            path = Path(d) / "officer.json"
            path.write_text(json.dumps(PACKET), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(read_officer_source(path, digest, SITE), PACKET)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_officer_source(path, "0" * 64, SITE)
            wrong_route = {**PACKET, "recipient_route_sha256": "0" * 64}
            path.write_text(json.dumps(wrong_route), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "recipient role or route"):
                read_officer_source(path, hashlib.sha256(path.read_bytes()).hexdigest(), SITE)
            bad = {**PACKET, "visible_camera_ids": ["front"]}
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "insufficient camera plan"):
                read_officer_source(path, hashlib.sha256(path.read_bytes()).hexdigest(), SITE)

    def test_actor_and_gesture_calls(self):
        calls = []
        world = World()
        value = construct(world, CARLA, PACKET, {"officer_direction": "proceed"},
                          lambda actor, asset, command: calls.append((actor.id, asset, command)))
        self.assertEqual(calls, [(99, "gesture.proceed", "proceed")])
        self.assertEqual(value["owned_actors"], [world.actor])
        bound = bind_recipient(PACKET, type("Bike", (), {"id": 22, "is_alive": True})(), SITE)
        self.assertEqual(read_command(world.actor, bound, 110,
                                      lambda actor, asset, frame: "proceed", "22")["command"], "proceed")
        with self.assertRaisesRegex(ValueError, "gesture readback missing"):
            read_command(world.actor, bound, 110, lambda actor, asset, frame: "none", "22")
        with self.assertRaisesRegex(ValueError, "outside source window"):
            read_command(world.actor, bound, 130, lambda actor, asset, frame: "proceed", "22")
        with self.assertRaisesRegex(ValueError, "recipient mismatch"):
            read_command(world.actor, bound, 110, lambda actor, asset, frame: "proceed", "23")
        with self.assertRaisesRegex(ValueError, "command differs"):
            construct(World(), CARLA, PACKET, {"officer_direction": "stop"}, lambda *args: None)

    def test_cleanup_on_gesture_failure(self):
        world = World()
        with self.assertRaisesRegex(ValueError, "gesture adapter failed"):
            construct(world, CARLA, PACKET, {"officer_direction": "proceed"},
                      lambda *args: (_ for _ in ()).throw(ValueError("gesture adapter failed")))
        self.assertTrue(world.actor.destroyed)


if __name__ == "__main__":
    unittest.main()

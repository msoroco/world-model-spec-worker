import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_spawn import read_asset_inventory, spawn_bicycle_and_rack


BIKE = "vehicle.test_human_bicycle"
RACK = "static.prop.test_bicycle_rack"


class Actor:
    def __init__(self, type_id, x, y):
        self.type_id = type_id
        self.destroyed = False
        self.transform = SimpleNamespace(location=SimpleNamespace(x=x, y=y))
        self.bounding_box = SimpleNamespace(get_world_vertices=lambda transform: [
            SimpleNamespace(x=x + dx, y=y + dy) for dx in (-.2, .2) for dy in (-.2, .2) for _ in (0, 1)])

    def get_transform(self):
        return self.transform

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, ids, fail_spawn=None):
        self.ids = ids
        self.fail_spawn = fail_spawn
        self.spawned = []

    def get_blueprint_library(self):
        return SimpleNamespace(find=lambda name: SimpleNamespace(id=name) if name in self.ids else None)

    def spawn_actor(self, bp, transform):
        if bp.id == self.fail_spawn:
            return None
        actor = Actor(bp.id, transform.location.x, transform.location.y)
        self.spawned.append(actor)
        return actor


CARLA = SimpleNamespace(Transform=lambda loc, rot: SimpleNamespace(location=loc, rotation=rot),
                        Location=lambda **kw: SimpleNamespace(**kw), Rotation=lambda **kw: SimpleNamespace(**kw))
SCENE = {"bicycle_blueprint_id": BIKE, "rack_blueprint_id": RACK}
INVENTORY = {"source_kind": "original_local_native_blueprint_inventory", "world_map": "test", "blueprint_ids": [BIKE, RACK]}


class NativeSpawnTest(unittest.TestCase):
    def test_gated_spawn_and_body_readback(self):
        bicycle, rack, actors = spawn_bicycle_and_rack(World([BIKE, RACK]), CARLA, SCENE, INVENTORY)
        self.assertEqual([actor.type_id for actor in actors], [BIKE, RACK])
        self.assertFalse(bicycle.destroyed or rack.destroyed)

    def test_inventory_without_rack_rejected(self):
        with self.assertRaisesRegex(ValueError, "inventory missing assets"):
            spawn_bicycle_and_rack(World([BIKE, RACK]), CARLA, SCENE,
                                   {**INVENTORY, "blueprint_ids": [BIKE]})

    def test_missing_native_rack_rejected(self):
        with self.assertRaisesRegex(ValueError, "Native blueprint unavailable"):
            spawn_bicycle_and_rack(World([BIKE]), CARLA, SCENE, INVENTORY)

    def test_rack_spawn_failure_cleans_bicycle(self):
        world = World([BIKE, RACK], fail_spawn=RACK)
        with self.assertRaisesRegex(RuntimeError, "rack spawn failed"):
            spawn_bicycle_and_rack(world, CARLA, SCENE, INVENTORY)
        self.assertTrue(world.spawned[0].destroyed)

    def test_inventory_hash_and_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(json.dumps(INVENTORY))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(read_asset_inventory(path, digest)["world_map"], "test")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                read_asset_inventory(path, "0" * 64)
            path.write_text(json.dumps({**INVENTORY, "source_kind": "synthetic_fixture"}))
            with self.assertRaisesRegex(ValueError, "source unverified"):
                read_asset_inventory(path, hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()

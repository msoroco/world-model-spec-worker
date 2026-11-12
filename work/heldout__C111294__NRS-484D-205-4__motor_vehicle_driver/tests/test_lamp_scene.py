import json
from pathlib import Path
from types import SimpleNamespace as N
import sys
import tempfile
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from lamp_scene import construct, discover_routes, drive_through, set_backup_lamp


def waypoint(x, y, yaw, road, lane, jid=None):
    loc = N(x=x, y=y)
    wp = N(transform=N(location=loc, rotation=N(yaw=yaw)),
           road_id=road, lane_id=lane)
    wp.get_junction = lambda: None if jid is None else N(id=jid)
    wp.previous = lambda distance: []
    wp.next = lambda distance: []
    return wp


def fake_map():
    east = waypoint(0, 0, 0, 1, 1, 42)
    north = waypoint(0, 0, 90, 2, 1, 42)
    for center, start, end in (
        (east, waypoint(-45, 0, 0, 1, 1), waypoint(35, 0, 0, 1, 1)),
        (north, waypoint(0, -45, 90, 2, 1), waypoint(0, 35, 90, 2, 1))):
        center.previous = lambda distance, start=start: [start]
        center.next = lambda distance, end=end: [end]
        start.next = lambda distance, center=center: [center]
    return N(generate_waypoints=lambda step: [east, north],
             get_waypoint=lambda location: east if location.x < 0 else north)


class FakeActor:
    def __init__(self, ident, transform):
        self.id, self.transform, self.bits, self.control, self.destroyed = ident, transform, 4, None, False
    def destroy(self): self.destroyed = True
    def get_transform(self): return self.transform
    def get_velocity(self): return N(x=0., y=0.)
    def apply_control(self, control): self.control = control
    def get_light_state(self): return self.bits
    def set_light_state(self, bits): self.bits = int(bits)


class TestLampScene(unittest.TestCase):
    def inventory(self, folder, count):
        path = folder/'inventory.json'
        path.write_text(json.dumps({'blueprint_id': 'vehicle.test',
            'inspection_method': 'asset_mesh_review', 'inspector': 'CPU fixture',
            'installed_backup_lamps': [
                {'location': 'rear', 'asset_source': 'fixture asset'} for _ in range(count)]}))
        return path

    def test_builds_two_perpendicular_routes_and_real_spawns(self):
        with tempfile.TemporaryDirectory() as tmp:
            world_map = fake_map(); spawns = []
            def spawn(bp, transform):
                actor = FakeActor(len(spawns)+1, transform)
                spawns.append(actor)
                return actor
            world = N(get_map=lambda: world_map,
                      get_blueprint_library=lambda: N(find=lambda name: N(id=name)),
                      try_spawn_actor=spawn)
            config = {'approach_m': 45., 'exit_m': 35.,
                      'ego_blueprint_id': 'vehicle.test',
                      'other_blueprint_id': 'vehicle.other',
                      'installed_backup_lamp_count': 1}
            scene = construct(world, N(), config, self.inventory(Path(tmp), 1))
            self.assertEqual(len(spawns), 2)
            self.assertEqual((spawns[0].transform.location.x,
                              spawns[1].transform.location.y), (-45, -45))
            self.assertNotEqual(scene['ego_route']['road_id'], scene['other_route']['road_id'])
            self.assertEqual(scene['equipment']['actor_id'], scene['ego'].id)
            carla = N(VehicleControl=lambda **kw: kw)
            drive_through(scene['ego'], world_map, carla, scene['ego_route'])
            self.assertGreater(scene['ego'].control['throttle'], 0)

    def test_rejects_ambiguous_or_missing_perpendicular_geometry(self):
        world_map = fake_map()
        world_map.generate_waypoints = lambda step: world_map.generate_waypoints_original(step) if False else []
        with self.assertRaisesRegex(ValueError, 'unambiguous'):
            discover_routes(world_map)

    def test_rejects_unsourced_inventory_and_cleans_failed_spawn(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self.inventory(Path(tmp), 1)
            config = {'approach_m': 45., 'exit_m': 35.,
                      'ego_blueprint_id': 'vehicle.test',
                      'other_blueprint_id': 'vehicle.other',
                      'installed_backup_lamp_count': 0}
            owned = []
            def spawn(bp, transform):
                if owned: return None
                actor = FakeActor(1, transform); owned.append(actor); return actor
            world = N(get_map=fake_map,
                      get_blueprint_library=lambda: N(find=lambda name: N(id=name)),
                      try_spawn_actor=spawn)
            with self.assertRaisesRegex(ValueError, 'inventory'):
                construct(world, N(), config, path)
            self.assertFalse(owned)
            config['installed_backup_lamp_count'] = 1
            with self.assertRaisesRegex(ValueError, 'other vehicle Native actor spawn failed'):
                construct(world, N(), config, path)
            self.assertTrue(owned[0].destroyed)

    def test_lamp_readback_preserves_other_bits_and_rejects_failure(self):
        actor = FakeActor(1, N())
        class LightState(int): Reverse = 8
        carla = N(VehicleLightState=LightState)
        self.assertTrue(set_backup_lamp(actor, carla, True))
        self.assertEqual(actor.bits, 12)
        self.assertFalse(set_backup_lamp(actor, carla, False))
        self.assertEqual(actor.bits, 4)
        actor.set_light_state = lambda bits: None
        with self.assertRaisesRegex(ValueError, 'readback mismatch'):
            set_backup_lamp(actor, carla, True)


if __name__ == '__main__': unittest.main()

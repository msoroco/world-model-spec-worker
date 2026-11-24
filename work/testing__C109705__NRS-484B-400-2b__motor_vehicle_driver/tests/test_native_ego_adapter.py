"""CPU fakes verify original CARLA readback and reviewed survey guards."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_ego_adapter', ROOT / 'native_ego_adapter.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Carla:
    Location = staticmethod(lambda **kw: NS(**kw))
    Rotation = staticmethod(lambda **kw: NS(**kw))
    Transform = staticmethod(lambda location, rotation: NS(location=location, rotation=rotation))
    VehicleControl = staticmethod(lambda **kw: NS(**kw))


class Ego:
    def __init__(self, transform):
        self.transform = transform
        self.control = NS(throttle=0, brake=0, steer=0)
        self.destroyed = False
        self.autopilot = None
        self.bounding_box = NS(get_world_vertices=lambda transform: [
            NS(x=transform.location.x + dx, y=transform.location.y + dy)
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1))])

    def set_autopilot(self, flag): self.autopilot = flag
    def apply_control(self, control): self.control = control
    def get_control(self): return self.control
    def get_transform(self): return self.transform
    def get_velocity(self): return NS(x=2, y=0, z=0)
    def destroy(self): self.destroyed = True


class Map:
    name = 'reviewed-town'
    def to_opendrive(self): return '<OpenDRIVE/>\n'
    def get_waypoint(self, location, project_to_road=True):
        return NS(road_id=4, transform=NS(location=location))


class World:
    def __init__(self):
        self.map = Map()
        self.frame = 0
        self.ego = None
    def get_map(self): return self.map
    def get_blueprint_library(self): return NS(find=lambda name: name)
    def try_spawn_actor(self, blueprint, transform):
        self.ego = Ego(transform)
        return self.ego
    def tick(self):
        self.frame += 1
        return self.frame
    def get_snapshot(self):
        return NS(frame=self.frame, timestamp=NS(elapsed_seconds=self.frame / 20))


def survey():
    boxes = {
        'approach': [[-10, -2], [-1, -2], [-1, 2], [-10, 2]],
        'intersection_entry': [[-1, -2], [1, -2], [1, 2], [-1, 2]],
        'turning': [[1, -2], [3, -2], [3, 2], [1, 2]],
        'departure': [[3, -2], [10, -2], [10, 2], [3, 2]],
    }
    return {'cell_id': 'C109705', 'maneuver': 'left_turn', 'map_name': 'reviewed-town',
            'source_sha256': hashlib.sha256(b'<OpenDRIVE/>\n').hexdigest(),
            'phase_regions': boxes, 'ego_blueprint_id': 'vehicle.test',
            'ego_spawn': {'xyz_m': [-5, 0, 0], 'rotation_deg': [0, 0, 0]},
            'route_waypoint_xy_m': {'17': [-4, 0]}}


class EgoAdapterTests(unittest.TestCase):
    def _make(self, root, *, changed_hash=False, changed_map=False):
        path = root / 'survey.json'
        path.write_text(json.dumps(survey()) + '\n')
        world = World()
        if changed_map:
            world.map.name = 'wrong-town'
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if changed_hash:
            sha = '0' * 64
        return world, module.NativeEgoAdapter(world, Carla, path, sha, case_id='case')

    def test_original_actor_control_and_snapshot_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            world, adapter = self._make(Path(directory))
            ego = adapter.spawn_ego('vehicle.test', 'reviewed-town', 'case')
            self.assertIs(ego, world.ego)
            self.assertFalse(ego.autopilot)
            self.assertEqual(adapter.resolve_waypoint(17), [-4.0, 0.0])
            adapter.apply_control(ego, {'throttle': .2, 'brake': 0, 'steer': .1})
            frame = adapter.tick()
            sample = adapter.ego_snapshot(ego, frame)
            self.assertEqual(sample['phase'], 'approach')
            self.assertEqual(sample['road_id'], 4)
            self.assertEqual(sample['elapsed_seconds'], .05)
            self.assertEqual(len(sample['body_corners_xy_m']), 4)
            adapter.emergency_stop(ego)
            adapter.destroy(ego)
            self.assertTrue(ego.destroyed)
            self.assertEqual(ego.control.brake, 1)

    def test_changed_survey_or_live_map_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, 'survey packet hash'):
                self._make(root, changed_hash=True)
            with self.assertRaisesRegex(ValueError, 'loaded Native map differs'):
                self._make(root, changed_map=True)

    def test_missing_camera_source_and_control_readback_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            _, adapter = self._make(Path(directory))
            ego = adapter.spawn_ego('vehicle.test', 'reviewed-town', 'case')
            with self.assertRaisesRegex(ValueError, 'NativeCameraSource'):
                adapter.configure_cameras(ego, ('dash', 'front', 'left', 'right'), 20)
            adapter.apply_control(ego, {'throttle': .2, 'brake': 0, 'steer': .1})
            ego.control.throttle = 0
            with self.assertRaisesRegex(ValueError, 'control readback'):
                adapter.ego_snapshot(ego, adapter.tick())


if __name__ == '__main__':
    unittest.main()

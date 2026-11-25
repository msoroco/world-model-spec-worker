"""Native handoff refuses unsurveyed signals and broken camera rigs."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N

from runner import copy_reviewed_bundle, install_four_cameras, original_signal_reader


def ref(root, name, value):
    path = root / name
    path.write_text(json.dumps(value) + '\n')
    return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class Signal:
    id = 7
    def get_state(self): return N(name='Green')


class World:
    def __init__(self): self.sensors = []
    def get_actor(self, identity): return Signal() if identity == 7 else None
    def get_blueprint_library(self): return N(find=lambda name: N(set_attribute=lambda key, value: None))
    def spawn_actor(self, blueprint, transform, attach_to=None):
        sensor = N(destroy=lambda: None)
        self.sensors.append((sensor, attach_to))
        return sensor


class NativeBindings(unittest.TestCase):
    def test_original_signal_shape_and_state_are_source_bound(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proof = {'official': True, 'head_id': 7, 'facing_approach_id': 'west',
                     'illuminated_shape': 'circular', 'enabled_indications': ['circular_green']}
            source = ref(root, 'signal-source.json', proof)
            site = {'signal_source_path': source['path'], 'original_sources': [source],
                    'official_head_id': 7, 'ego_approach_id': 'west'}
            self.assertEqual(original_signal_reader(World(), site, root)(N(frame=3), 7)['lit_aspects'],
                             ['circular_green'])
            proof['illuminated_shape'] = 'arrow'
            source = ref(root, 'signal-source.json', proof)
            site['original_sources'] = [source]
            with self.assertRaisesRegex(ValueError, 'circular-only'):
                original_signal_reader(World(), site, root)

    def test_four_source_surveyed_cameras_are_created(self):
        world = World()
        ego = object()
        names = ('overview','approach','reference_corner','driver_reference')
        site = {'camera_poses': {name: {'x':0,'y':0,'z':10,'pitch':-30,'yaw':0,
                                         'roll':0,'fov_deg':90} for name in names}}
        carla = N(Location=lambda **kw: kw, Rotation=lambda **kw: kw,
                  Transform=lambda location, rotation: (location, rotation))
        cameras = install_four_cameras(world, ego, site, carla)
        self.assertEqual(set(cameras), set(names))
        self.assertIs(world.sensors[-1][1], ego)
        site['camera_poses'].pop('overview')
        with self.assertRaisesRegex(ValueError, 'four source-surveyed'):
            install_four_cameras(world, ego, site, carla)

    def test_reviewed_bundle_hashes_and_content_are_required(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / 'bundle'
            output = Path(directory) / 'attempt'
            bundle.mkdir();output.mkdir()
            sources = [ref(bundle, name, {'original':name}) for name in
                       ('site.json','camera-profile.json','other-devices.json')]
            (bundle / 'bundle-index.json').write_text(json.dumps({'sources':sources}) + '\n')
            copy_reviewed_bundle(bundle, output)
            self.assertEqual(sorted(p.name for p in output.iterdir()), sorted(r['path'] for r in sources))
            (output / 'site.json').unlink()
            (bundle / 'site.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'source hash'):
                copy_reviewed_bundle(bundle, output)


if __name__ == '__main__': unittest.main()

"""Synchronous world and six-actor ownership around exact capture."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from live_crosswalk import run
from test_carla_adapter import Actor, World
from test_native_capture import SCENE, packet, png


class OwnedActor(Actor):
    def __init__(self, actor_id, xy):
        super().__init__(actor_id, xy)
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class LeaseWorld(World):
    def __init__(self):
        super().__init__()
        self.current = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=.1)

    def get_settings(self):
        return SimpleNamespace(**vars(self.current))

    def apply_settings(self, settings):
        self.current = SimpleNamespace(**vars(settings))


class LiveCrosswalkTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work' / 'c111610-live-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = self.root / 'site.json'
        self.site.write_text(json.dumps(packet()) + '\n')
        self.exception = self.root / 'exception.json'
        self.exception.write_text(json.dumps({
            'case_id': json.loads(SCENE.read_text())['case_id'],
            'status': 'none_identified', 'source_refs': ['review/exception-source.json']}) + '\n')
        self.world = LeaseWorld()
        self.client = SimpleNamespace(get_world=lambda: self.world)
        self.actors = []

    def factory(self, *, register, **_):
        ego = register(OwnedActor(101, [0, -2]))
        person = register(OwnedActor(202, [1, 2]))
        cameras = {name: register(OwnedActor(300 + index, [0, 0]))
                   for index, name in enumerate(('overview', 'approach',
                                                 'reference_corner', 'driver_reference'))}
        self.actors = [ego, person, *cameras.values()]
        body = png()
        readers = {name: lambda frame, image=body: {'frame': frame, 'png_bytes': image}
                   for name in cameras}
        return {'ego': ego, 'pedestrian': person, 'sensors': cameras,
                'camera_readers': readers, 'controller': lambda *_: None}

    def test_complete_capture_restores_world_and_destroys_actors(self):
        result = run(self.client, SCENE, self.site, self.exception,
                     self.root / 'attempt', self.factory,
                     dimensions={name: (2, 2) for name in
                                 ('overview', 'approach', 'reference_corner', 'driver_reference')})
        self.assertEqual(result['physical_acceptance'], 'unverified')
        self.assertTrue((self.root / 'attempt/source-index.json').is_file())
        self.assertTrue(all(actor.destroyed for actor in self.actors))
        self.assertFalse(self.world.current.synchronous_mode)
        self.assertEqual(self.world.current.fixed_delta_seconds, .1)

    def test_partial_factory_failure_releases_registered_actors(self):
        def fail(**kwargs):
            self.actors = [kwargs['register'](OwnedActor(101, [0, 0]))]
            raise ValueError('source review rejected')
        with self.assertRaisesRegex(ValueError, 'source review rejected'):
            run(self.client, SCENE, self.site, self.exception,
                self.root / 'attempt', fail)
        self.assertTrue(self.actors[0].destroyed)
        self.assertFalse(self.world.current.synchronous_mode)


if __name__ == '__main__':
    unittest.main()

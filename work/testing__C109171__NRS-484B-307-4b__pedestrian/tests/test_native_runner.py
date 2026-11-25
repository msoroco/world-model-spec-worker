import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_runner import run_capture
from native_scene import SourceError


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.applied = []

    def get_settings(self):
        return self.settings

    def apply_settings(self, settings):
        self.settings = settings
        self.applied.append((settings.synchronous_mode, settings.fixed_delta_seconds))


class RunnerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work')
        self.root = Path(self.tmp.name)
        (self.root / 'map.json').write_bytes(b'{"surveyed": true}')
        (self.root / 'survey-road.xodr').write_bytes(b'<OpenDRIVE/>')
        (self.root / 'site.json').write_text(json.dumps({
            'map_source_path': 'map.json', 'road_xodr_source_path': 'survey-road.xodr',
            'original_sources': [{'path': 'survey-road.xodr'}]}))
        self.ref = {'path': 'site.json',
                    'sha256': hashlib.sha256((self.root / 'site.json').read_bytes()).hexdigest()}
        self.world = World()
        self.kwargs = dict(attempt=self.root, site_ref=self.ref,
                           permission_review_ref={'path': 'review.json', 'sha256': 'fixture'},
                           case_id='case',
                           map_reader=lambda world: (self.root / 'survey-road.xodr').read_bytes(),
                           walker=object(), sensors={}, original_state_reader=object(),
                           walker_control_factory=object(), vector_factory=object(),
                           expected_frames=3)

    def tearDown(self):
        self.tmp.cleanup()

    def test_borrowed_clock_restored_after_capture(self):
        with patch('native_runner.verify_site'), patch('native_runner.validate_permission_review'), \
             patch('native_runner.CarlaAdapter') as adapter, \
             patch('native_runner.capture', return_value={'frame_count': 3}) as capture:
            result = run_capture(self.world, **self.kwargs)
        self.assertEqual(result['frame_count'], 3)
        self.assertEqual(self.world.applied, [(True, 0.05), (False, None)])
        self.assertEqual(capture.call_args.args[-2], 'case')
        adapter.return_value.close.assert_called()

    def test_restores_clock_when_capture_fails(self):
        with patch('native_runner.verify_site'), patch('native_runner.validate_permission_review'), \
             patch('native_runner.CarlaAdapter') as adapter, \
             patch('native_runner.capture', side_effect=ValueError('capture failed')):
            with self.assertRaisesRegex(ValueError, 'capture failed'):
                run_capture(self.world, **self.kwargs)
        self.assertEqual(self.world.applied[-1], (False, None))
        adapter.return_value.close.assert_called()

    def test_rejects_changed_loaded_map_before_world_mutation(self):
        self.kwargs['map_reader'] = lambda world: b'not surveyed map'
        with patch('native_runner.verify_site'), patch('native_runner.validate_permission_review'):
            with self.assertRaisesRegex(SourceError, 'loaded Native map differs'):
                run_capture(self.world, **self.kwargs)
        self.assertEqual(self.world.applied, [])

    def test_rejects_missing_permission_review_before_world_mutation(self):
        with patch('native_runner.verify_site'), patch('permission_applicability.verify_site'):
            with self.assertRaisesRegex(SourceError, 'review source missing'):
                run_capture(self.world, **self.kwargs)
        self.assertEqual(self.world.applied, [])


if __name__ == '__main__':
    unittest.main()

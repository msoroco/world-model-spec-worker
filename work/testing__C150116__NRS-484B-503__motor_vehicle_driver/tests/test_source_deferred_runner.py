"""Exercise source preflight and the actual original capture call path."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from source_deferred_runner import CAMERAS, capture_original
from finalize_original_delivery import finalize


class Adapter:
    def __init__(self, case, site=None):
        self.case = case
        self.site = site
        self.calls = []
        self.actors = []
        self.attempt = None

    def provenance(self):
        self.calls.append('provenance')
        return 'original_native'

    def pipeline_client(self):
        self.calls.append('pipeline_client')
        return self

    def spawn_vehicle(self, *args, **kwargs):
        self.calls.append('spawn_vehicle')
        self.actors.append('ego')
        return 'ego'

    def spawn_passenger(self, *args, **kwargs):
        self.calls.append('spawn_passenger')
        self.actors.append('passenger')
        return 'passenger'

    def set_route(self, *args):
        self.calls.append('set_route')

    def set_conduct(self, *args):
        self.calls.append('set_conduct')

    def set_passenger_action(self, *args, **kwargs):
        self.calls.append('set_passenger_action')

    def start_cameras(self, attempt, names):
        self.calls.append('start_cameras')
        self.attempt = attempt
        assert tuple(names) == CAMERAS

    def tick_and_sample(self):
        index = self.calls.count('tick')
        self.calls.append('tick')
        return {'case_id': self.case, 'original_frame': 1000 + index, 'elapsed_s': index / 20,
                'ego_id': 'ego', 'passenger_id': 'passenger', 'map_sha256': 'a',
                'zone_source_sha256': self.site['zone']['boundary_source_sha256'] if self.site else 'b',
                'regulations_source_sha256': self.site['regulations']['source_sha256'] if self.site else 'c',
                'clock_source_sha256': 'd', 'source_sha256': 'e',
                'camera_plan_sha256': 'fake-camera-plan', 'control_source_sha256': 'f', 'ego_center_xy': [2, 0],
                'ego_speed_mps': 0.0, 'passenger_event': None}

    def record_camera_frame(self, row):
        self.calls.append('camera')
        return {name: row['original_frame'] for name in CAMERAS}

    def finish_cameras(self):
        self.calls.append('finish_cameras')
        for name in CAMERAS:
            (self.attempt / (name + '.mkv')).write_bytes(b'original-fake-camera')
        return {name: self.attempt / (name + '.mkv') for name in CAMERAS}

    def finish_native_capture(self, attempt, rows):
        self.calls.append('finish_native_capture')
        return []

    def abort_cameras(self):
        self.calls.append('abort_cameras')

    def destroy(self, actor):
        self.calls.append('destroy')
        self.actors.remove(actor)

    def restore_world(self):
        self.calls.append('restore_world')
        return True


class SourceDeferredRunnerTests(unittest.TestCase):
    def test_missing_source_never_touches_adapter(self):
        class Untouched:
            def __getattr__(self, _):
                raise AssertionError('Native adapter touched before original source')
        fixture = json.loads((HERE / 'construction-diagnostic-load_prompt.json').read_text())
        files = {item['path']: item['content'] for item in fixture['files']}
        scratch = ROOT / '.runtime-work/c150116-new/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            (root / 'config.json').write_text(files['config.json'])
            (root / 'scene.json').write_text(files['scene.json'])
            with self.assertRaisesRegex(ValueError, 'reviewed original passenger-zone site source missing'):
                capture_original(Untouched(), root / 'missing-manifest', root / 'missing-site',
                                 root / 'missing-attempt', root)

    def test_original_fake_adapter_call_path(self):
        fixture = json.loads((HERE / 'construction-diagnostic-load_prompt.json').read_text())
        files = {item['path']: item['content'] for item in fixture['files']}
        site = json.loads(files['scene.json'])
        site['source_kind'] = 'reviewed_original_site'
        site['reviewer'] = 'fake CPU protocol reviewer'
        site['zone']['passenger_anchor_source_sha256'] = 'fake-original-source-hash'
        case_id = HERE.name + '__load_prompt'
        scratch = ROOT / '.runtime-work/c150116-new/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            attempt = root / 'attempt'
            attempt.mkdir()
            (root / 'config.json').write_text(files['config.json'])
            (root / 'scene.json').write_text(files['scene.json'])
            for name in ('construction.json', 'runner.py', 'config.json'):
                (attempt / name).write_text('{}\n')
            site_path = root / 'site-context.json'
            site_path.write_text(json.dumps(site) + '\n')
            manifest_path = root / 'source-manifest.json'
            manifest_path.write_text(json.dumps({'source_kind': 'reviewed_original_site',
                'diagnostic_fixture': False, 'reviewer': 'fake CPU protocol reviewer',
                'source_provenance': {'kind': 'original_reviewed_site',
                    'diagnostic_fixture': False, 'reviewer': 'fake CPU protocol reviewer',
                    'citation': 'synthetic fake-adapter protocol test only'},
                'case_id': case_id, 'files': {'site-context.json': {
                    'sha256': hashlib.sha256(site_path.read_bytes()).hexdigest()}}}) + '\n')
            adapter = Adapter('load_prompt', site)
            class FakePipeline:
                def __init__(self, client, ego, output, case_id, **kwargs):
                    self.closed = False
                    self.client = client
                    self.output = output
                    self.rows = []

                def capture(self, frame, time_s):
                    self.client.calls.append('pipeline_capture')
                    self.rows.append((frame, time_s))
                    return {'frame': frame, 'time_s': time_s}

                def close(self, confirmed=True):
                    self.client.calls.append('pipeline_close')
                    self.closed = True
                    (self.output / 'trace.jsonl').write_text('{}\n')
                    (self.output / 'road.xodr').write_text('<OpenDRIVE/>\n')
                    (self.output / 'carla_recorder.log').write_text('fake recorder\n')
                    capture = self.output / 'capture'
                    capture.mkdir()
                    (capture / 'manifest.json').write_text('{}\n')
            result = capture_original(adapter, manifest_path, site_path, attempt,
                                      root, pipeline_factory=FakePipeline)
            self.assertEqual(result['frame_count'], 900)
            self.assertEqual(adapter.calls.count('tick'), 900)
            self.assertEqual(adapter.calls.count('camera'), 900)
            self.assertEqual(adapter.calls.count('pipeline_capture'), 900)
            self.assertEqual(adapter.actors, [])
            self.assertIn('restore_world', adapter.calls)
            seal = json.loads((attempt / 'capture-seal.json').read_text())
            self.assertEqual(set(seal['sources']) & {name + '.mkv' for name in CAMERAS},
                             {name + '.mkv' for name in CAMERAS})
            self.assertFalse(seal['diagnostic_fixture'])
            finalized = finalize(attempt, case_id)
            self.assertEqual(finalized['case_id'], case_id)
            self.assertTrue((attempt / 'source-manifest.json').is_file())
            broken_attempt = root / 'broken-attempt'
            broken_attempt.mkdir()
            for name in ('construction.json', 'runner.py', 'config.json'):
                (broken_attempt / name).write_text('{}\n')
            class BrokenAdapter(Adapter):
                def record_camera_frame(self, row):
                    self.calls.append('camera')
                    return {'overview': row['original_frame']}
            broken = BrokenAdapter('load_prompt')
            with self.assertRaisesRegex(ValueError, 'four original camera frames not joined'):
                capture_original(broken, manifest_path, site_path, broken_attempt,
                                 root, pipeline_factory=FakePipeline)
            self.assertEqual(broken.actors, [])
            self.assertIn('abort_cameras', broken.calls)
            self.assertIn('restore_world', broken.calls)
            self.assertFalse((broken_attempt / 'capture-seal.json').exists())

    def test_original_source_provenance_rejected_before_adapter(self):
        fixture = json.loads((HERE / 'construction-diagnostic-load_prompt.json').read_text())
        files = {item['path']: item['content'] for item in fixture['files']}
        scratch = ROOT / '.runtime-work/c150116-new/tmp'
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            (root / 'config.json').write_text(files['config.json'])
            (root / 'scene.json').write_text(files['scene.json'])
            site = root / 'site-context.json'
            site.write_text('{}\n')
            manifest = root / 'source-manifest.json'
            manifest.write_text(json.dumps({'source_kind': 'reviewed_original_site',
                'diagnostic_fixture': False, 'reviewer': 'fake',
                'case_id': HERE.name + '__load_prompt',
                'files': {'site-context.json': {'sha256': hashlib.sha256(site.read_bytes()).hexdigest()}}}) + '\n')
            class Untouched:
                def __getattr__(self, _):
                    raise AssertionError('adapter touched before source provenance check')
            with self.assertRaisesRegex(ValueError, 'original reviewed site provenance missing'):
                capture_original(Untouched(), manifest, site, root / 'attempt', root)


if __name__ == '__main__':
    unittest.main()

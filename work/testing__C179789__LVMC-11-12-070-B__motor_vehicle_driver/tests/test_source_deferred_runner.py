"""Focused checks for original Native source gating and exact preflight."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import source_deferred_runner as runner
from original_runner import REQUIRED, load_reviewed_site


class RunnerTests(unittest.TestCase):
    def test_root_selected_preflight(self):
        case_id, name = runner.check(HERE)
        self.assertEqual(case_id, HERE.name + '__' + name)
        self.assertEqual(name, 'cross_yield')

    def test_missing_reviewed_packet_fails_before_native_use(self):
        class Adapter:
            def provenance(self):
                raise AssertionError('Native adapter reached before reviewed source gate')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('construction.json', 'runner.py', 'config.json'):
                (root / name).write_text(name + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original site packet missing'):
                runner.capture_original(Adapter(), root / 'missing-manifest.json',
                                        root / 'missing-site.json', root, HERE)

    def test_synthetic_packet_rejected_for_original_capture(self):
        class Adapter:
            def provenance(self):
                raise AssertionError('Native adapter reached with synthetic source')

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('construction.json', 'runner.py', 'config.json'):
                (root / name).write_text(name + '\n')
            site = json.loads((HERE / 'scene.json').read_text())
            (root / 'site.json').write_text(json.dumps(site) + '\n')
            (root / 'manifest.json').write_text(json.dumps({
                'format': 'reviewed-through-highway-site-v1',
                'case_id': HERE.name + '__cross_yield',
                'source_kind': 'synthetic_diagnostic_fixture'}) + '\n')
            with self.assertRaisesRegex(ValueError, 'reviewed original site identity/provenance missing'):
                runner.capture_original(Adapter(), root / 'manifest.json',
                                        root / 'site.json', root, HERE)

    def test_reviewed_packet_is_source_hashed_and_case_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sources = {}
            for name in REQUIRED:
                path = root / name
                path.write_text('reviewed source ' + name + '\n')
                sources[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            site = json.loads((HERE / 'scene.json').read_text())
            site.update(source_kind='reviewed_original_site', accepted_original_source=True,
                        map_sha256=sources['road.xodr']['sha256'])
            for name, field in (('municipal_jurisdiction', 'municipal_jurisdiction_source'),
                                ('through_highway_designation', 'through_highway_designation_source'),
                                ('intersection_geometry', 'intersection_geometry_source'),
                                ('entrance_control', 'entrance_control_source'),
                                ('antecedent_review', 'antecedent_review_source')):
                site[field] = sources[name]['sha256']
            site_path = root / 'site.json'
            site_path.write_text(json.dumps(site) + '\n')
            manifest = {'format': 'reviewed-through-highway-site-v1',
                        'case_id': HERE.name + '__cross_yield', 'reviewer': 'fixture reviewer',
                        'citation': 'synthetic protocol test only', 'source_kind': 'reviewed_original_site',
                        'site_sha256': hashlib.sha256(site_path.read_bytes()).hexdigest(),
                        'sources': sources}
            manifest_path = root / 'manifest.json'
            manifest_path.write_text(json.dumps(manifest) + '\n')
            self.assertEqual(load_reviewed_site(manifest_path, site_path, manifest['case_id'])['case_id'], manifest['case_id'])
            (root / 'antecedent_review').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'source seal changed'):
                load_reviewed_site(manifest_path, site_path, manifest['case_id'])

    def test_fake_native_call_path_joins_900_ticks_and_copies_reviewed_sources(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / 'attempt'
            output.mkdir()
            for name in ('construction.json', 'runner.py', 'config.json'):
                (output / name).write_text(name + '\n')
            adapter_module = root / 'native_adapter.py'
            adapter_module.write_text('def open_native_adapter(): pass\n')
            sources = {}
            for name in REQUIRED:
                path = root / name
                path.write_text('fake reviewed source ' + name + '\n')
                sources[name] = {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            site_path = root / 'site.json'
            site = json.loads((HERE / 'scene.json').read_text())
            site_path.write_text(json.dumps(site) + '\n')
            manifest_path = root / 'manifest.json'
            manifest_path.write_text(json.dumps({'sources': sources,
                'native_adapter_sha256': hashlib.sha256(adapter_module.read_bytes()).hexdigest()}) + '\n')

            class Actor:
                def __init__(self):
                    self.destroyed = False
                def destroy(self):
                    self.destroyed = True

            through, entering = Actor(), Actor()
            built = {'actors': {'through': through, 'entering': entering},
                     'routes': site['routes'], 'request': 'yield_request'}

            class World:
                frame = 99
                def get_snapshot(self):
                    return type('Snapshot', (), {'frame': self.frame,
                        'timestamp': type('Timestamp', (), {'elapsed_seconds': (self.frame - 100) / 20})()})()

            class Adapter:
                def __init__(self):
                    self.w = World()
                    self.restored = False
                def provenance(self): return 'original_native'
                def world(self): return self.w
                def pipeline_client(self): return object()
                def start_cameras(self, attempt, cameras):
                    self.cameras = tuple(cameras)
                def tick_world(self): self.w.frame += 1
                def camera_frame_ids(self, frame): return {name: frame for name in runner.CAMERAS}
                def finish_cameras(self):
                    paths = {}
                    for name in runner.CAMERAS:
                        path = output / (name + '.mkv')
                        path.write_bytes(b'fake diagnostic video')
                        paths[name] = path
                    return paths
                def finish_native_capture(self, attempt, rows):
                    for name in ('road.xodr', 'trace.jsonl', 'carla_recorder.log'):
                        (attempt / name).write_text('fake diagnostic source\n')
                    return []
                def restore_world(self):
                    self.restored = True
                    return True

            class Pipeline:
                def __init__(self, client, actor, attempt, case_id, required_observations=()):
                    self.closed = False
                    self.count = 0
                def capture(self, frame, elapsed):
                    self.count += 1
                    return {'frame': frame, 'time_s': elapsed}
                def close(self, confirmed):
                    self.closed = True
                    (output / 'capture/native').mkdir(parents=True, exist_ok=True)
                    (output / 'capture/native/frames.jsonl').write_text('fake diagnostic frame\n')

            def sample(world, actors, source, key, map_sha, index, first_elapsed):
                return {'frame_index': index, 'native_frame': world.frame,
                        'time_s': index / 20, 'map_sha256': source['map_sha256'],
                        'intersection_id': source['intersection_id']}

            adapter = Adapter()
            with mock.patch.object(runner, 'load_reviewed_site', return_value=site), \
                 mock.patch.object(runner, 'construct', return_value=built), \
                 mock.patch.object(runner, 'control_tick', return_value={}), \
                 mock.patch.object(runner, 'sample_native_frame', side_effect=sample), \
                 mock.patch.object(runner, 'measure', return_value={'original_frame_count': 900}):
                result = runner.capture_original(adapter, manifest_path, site_path, output,
                                                 HERE, Pipeline, adapter_module)
            self.assertEqual(result['frame_count'], 900)
            self.assertEqual(len((output / 'camera-frame-map.jsonl').read_text().splitlines()), 900)
            self.assertTrue((output / 'reviewed-site/native-adapter.py').is_file())
            self.assertTrue((output / 'reviewed-site/antecedent_review').is_file())
            self.assertTrue(adapter.restored and through.destroyed and entering.destroyed)
            seal = json.loads((output / 'capture-seal.json').read_text())
            self.assertEqual(seal['native_revision']['runner_sha256'], hashlib.sha256((output / 'runner.py').read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()

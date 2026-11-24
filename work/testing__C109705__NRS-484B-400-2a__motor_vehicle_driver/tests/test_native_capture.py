import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from native_capture import capture, _checked_graph
from core_packet import project as project_core_packet
from runner import run_capture
from approach import measure
from analysis import finalize
from saved_delivery import audit, audit_original_pixels
from test_approach import body, context
from test_native_map import CASE, FakeWorld


buffer = io.BytesIO()
Image.new('RGB', (2, 2), color=(12, 34, 56)).save(buffer, format='PNG')
PNG = buffer.getvalue()
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


class FakeAdapter:
    def __init__(self, *, drift_at=None, camera_drift_at=None, omit_camera=None, invalid_png=False,
                 cleanup_failure=False, disconnect_on_cleanup=False):
        self.world = FakeWorld()
        self.count = 0
        self.drift_at = drift_at
        self.camera_drift_at = camera_drift_at
        self.omit_camera = omit_camera
        self.invalid_png = invalid_png
        self.cleanup_failure = cleanup_failure
        self.disconnect_on_cleanup = disconnect_on_cleanup
        self.braked = False
        self.cleaned = False
        self.native_attested = False

    def start(self, plan):
        self.case_id = plan['case_id']

    def tick(self):
        index = self.count
        self.count += 1
        return {'frame': 100 + index,
                'time_s': index * .05 + (0.02 if index == self.drift_at else 0)}

    def read_ego(self, frame):
        index = frame - 100
        phase = 'approach' if index < 450 else 'departure'
        return {'frame': frame, 'case_id': self.case_id, 'phase': phase,
                'road_id': phase, 'ego_heading_rad': 0.0 if index < 450 else 1.2,
                'ego_body_vertices_xy_m': body(-.7)}

    def read_cameras(self, frame):
        raw = b'\x89PNG\r\n\x1a\n' + b'bad-image' if self.invalid_png else PNG
        return {name: {'frame': frame, 'time_s': (frame - 100) * .05 +
                       (.02 if frame - 100 == self.camera_drift_at else 0), 'png': raw}
                for name in CAMERAS if name != self.omit_camera}

    def brake(self):
        self.braked = True

    def cleanup(self):
        self.cleaned = True
        if self.disconnect_on_cleanup:
            self.world = None
        if self.cleanup_failure:
            raise RuntimeError('adapter cleanup failure')


def packet(path):
    source = '<OpenDRIVE>surveyed</OpenDRIVE>'
    value = {'context': context(), 'map_name': 'TownTest',
             'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
             'left_turn_route_waypoint_ids': [11, 12, 13],
             'ego_blueprint_id': 'vehicle.test',
             'camera_plan': 'four cameras, 20 Hz'}
    path.write_text(json.dumps(value))


class NativeCaptureTests(unittest.TestCase):
    def test_graph_envelope_rejects_duplicate_and_invalid_edges(self):
        graph = {'format': 'native-adapter-graph-v1', 'multigraph': False,
                 'metadata': {'frame': 100, 'simulation_time_s': 0.0},
                 'nodes': [{'id': 'ego', 'attributes': {}},
                           {'id': 'other', 'attributes': {}}],
                 'edges': [{'source': 0, 'target': 1, 'attributes': {}}]}
        _checked_graph(json.dumps(graph).encode(), 100, 0.0)
        graph['nodes'][1]['id'] = 'ego'
        with self.assertRaisesRegex(ValueError, 'duplicated'):
            _checked_graph(json.dumps(graph).encode(), 100, 0.0)
        graph['nodes'][1]['id'] = 'other'
        graph['edges'][0]['target'] = True
        with self.assertRaisesRegex(ValueError, 'edge malformed'):
            _checked_graph(json.dumps(graph).encode(), 100, 0.0)

    def test_original_adapter_graphs_join_core_packet_and_reject_tamper(self):
        class GraphAdapter(FakeAdapter):
            def read_graph(self, frame):
                graph = {'format': 'native-adapter-graph-v1', 'multigraph': False,
                         'metadata': {'frame': frame,
                                      'simulation_time_s': (frame - 100) * .05},
                         'nodes': [{'id': 'ego', 'attributes': {'actor_id': 7}}],
                         'edges': []}
                return json.dumps(graph, separators=(',', ':')).encode()

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(GraphAdapter(), CASE, survey, attempt)
            receipt = project_core_packet(attempt, root / 'core-packet')
            self.assertFalse(receipt['graph_capture_required'])
            self.assertEqual(len(list((root / 'core-packet/graphs/abstract').glob('*.adapter.json'))), 900)
            self.assertEqual(json.loads((root / 'core-packet/graphs/abstract/00000100.adapter.json').read_text())['metadata']['frame'], 100)
            original = attempt / 'graphs/abstract/00000100.adapter.json'
            original.write_bytes(original.read_bytes() + b' ')
            with self.assertRaisesRegex(ValueError, 'graph source hash differs'):
                project_core_packet(attempt, root / 'tampered-core-packet')
            self.assertFalse((root / 'tampered-core-packet').exists())

    def test_attested_adapter_requires_original_graph_callback(self):
        adapter = FakeAdapter()
        adapter.native_attested = True
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            with self.assertRaisesRegex(ValueError, 'requires original adapter graph'):
                capture(adapter, CASE, survey, root / 'attempt')
            self.assertFalse((root / 'attempt').exists())

    def test_diagnostic_core_packet_publish_is_atomic(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            from core_packet import _save
            calls = 0

            def fail_second_save(path, rows):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError('injected second file failure')
                return _save(path, rows)

            with mock.patch('core_packet._save', side_effect=fail_second_save):
                with self.assertRaisesRegex(OSError, 'injected second file failure'):
                    project_core_packet(attempt, root / 'core-packet')
            self.assertFalse((root / 'core-packet').exists())
            self.assertFalse(list(root.glob('core-packet.incomplete-*')))
            receipt = project_core_packet(attempt, root / 'core-packet')
            self.assertEqual(receipt['frames'], 900)

    def test_diagnostic_core_packet_joins_saved_original_frames(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            receipt = project_core_packet(attempt, root / 'core-packet')
            self.assertEqual(receipt['frames'], 900)
            self.assertEqual(receipt['source_sha256']['road.xodr'],
                             hashlib.sha256((attempt / 'road.xodr').read_bytes()).hexdigest())
            self.assertTrue(receipt['graph_capture_required'])
            self.assertFalse(receipt['physical_completion'])
            trace = [json.loads(line) for line in (root / 'core-packet/trace.jsonl').read_text().splitlines()]
            evidence = [json.loads(line) for line in
                        (root / 'core-packet/capture/evidence.jsonl').read_text().splitlines()]
            frames = [json.loads(line) for line in
                      (root / 'core-packet/capture/native/frames.jsonl').read_text().splitlines()]
            self.assertEqual([row['frame'] for row in trace],
                             [row['original_frame'] for row in evidence])
            self.assertEqual([row['frame'] for row in trace], [row['frame'] for row in frames])
            self.assertTrue(all(row['ego']['speed_provenance'] == 'synthetic_native_sample'
                                for row in evidence))
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                project_core_packet(attempt, root / 'core-packet')
            original = attempt / 'approach-history.jsonl'
            original.write_bytes(original.read_bytes() + b'{}\n')
            with self.assertRaisesRegex(ValueError, 'hash|Hash|source'):
                project_core_packet(attempt, root / 'tampered')

    def test_diagnostic_core_packet_rejects_changed_original_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            (attempt / 'road.xodr').write_bytes(b'<OpenDRIVE>changed</OpenDRIVE>')
            with self.assertRaisesRegex(ValueError, 'hash|Hash|source'):
                project_core_packet(attempt, root / 'core-packet')
            self.assertFalse((root / 'core-packet').exists())

    def test_diagnostic_core_packet_rejects_sealed_short_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            acquisition_path = attempt / 'acquisition.json'
            acquisition = json.loads(acquisition_path.read_text())
            for name in ('approach-history.jsonl', 'video_frames.jsonl'):
                source = attempt / name
                source.write_bytes(b'\n'.join(source.read_bytes().splitlines()[:899]) + b'\n')
                acquisition[name]['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            acquisition_path.write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'complete original capture'):
                project_core_packet(attempt, root / 'core-packet')
            self.assertFalse((root / 'core-packet').exists())

    def test_diagnostic_core_packet_rejects_resealed_bad_original_pixel(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            source = attempt / 'approach.zip'
            with zipfile.ZipFile(source) as archive:
                images = [(name, archive.read(name)) for name in archive.namelist()]
            with zipfile.ZipFile(source, 'w', compression=zipfile.ZIP_STORED) as archive:
                for index, (name, raw) in enumerate(images):
                    archive.writestr(name, b'corrupt png' if index == 0 else raw)
            acquisition_path = attempt / 'acquisition.json'
            acquisition = json.loads(acquisition_path.read_text())
            acquisition['media']['approach']['sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            acquisition_path.write_text(json.dumps(acquisition))
            with self.assertRaises((ValueError, OSError)):
                project_core_packet(attempt, root / 'core-packet')
            self.assertFalse((root / 'core-packet').exists())

    def test_exact_bundle_runner_uses_reviewed_native_capture(self):
        package = Path(__file__).resolve().parents[1]
        construction = json.loads((package / 'cases/near_centerline/construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            result = run_capture(FakeAdapter(), config, survey, root / 'attempt')
            self.assertEqual(result['frame_count'], 900)
            self.assertTrue((root / 'attempt' / 'road.xodr').is_file())

    def test_full_diagnostic_capture_and_saved_reopen(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            adapter = FakeAdapter()
            result = capture(adapter, CASE, survey, root / 'attempt')
            self.assertEqual(result['frame_count'], 900)
            original_map = (root / 'attempt' / 'road.xodr').read_bytes()
            self.assertEqual(original_map, b'<OpenDRIVE>surveyed</OpenDRIVE>')
            acquisition = json.loads((root / 'attempt' / 'acquisition.json').read_text())
            self.assertEqual(acquisition['road.xodr']['sha256'],
                             hashlib.sha256(original_map).hexdigest())
            frames = [json.loads(line) for line in
                      (root / 'attempt' / 'video_frames.jsonl').read_text().splitlines()]
            self.assertEqual(len(frames), 900)
            self.assertEqual([(row['video_frame'], row['carla_frame'],
                               row['native_frame'], row['frame']) for row in frames],
                             [(index, 100 + index, 100 + index, 100 + index)
                              for index in range(900)])
            self.assertTrue(all(set(row['camera_times_s']) == set(CAMERAS)
                                and all(abs(value - row['time_s']) < .001
                                        for value in row['camera_times_s'].values())
                                for row in frames))
            self.assertTrue(adapter.braked and adapter.cleaned)
            with self.assertRaisesRegex(ValueError, 'diagnostic'):
                audit(root / 'attempt', CASE)
            reopened = audit(root / 'attempt', CASE, allow_diagnostic=True)
            self.assertTrue(reopened['source_integrity_passed'])
            self.assertFalse(reopened['physical_completion'])
            pixels = audit_original_pixels(root / 'attempt', CASE, allow_diagnostic=True)
            self.assertEqual(pixels['decoded_frames'], 3600)
            self.assertEqual(pixels['dimensions']['approach'], [2, 2])
            self.assertFalse(pixels['physical_completion'])

    def test_frame_drift_and_missing_camera_are_rejected_with_cleanup(self):
        for kwargs, error in (({'drift_at': 4}, 'cadence'),
                              ({'camera_drift_at': 4}, 'camera timestamp drift'),
                              ({'omit_camera': 'approach'}, 'four-camera')):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                survey = root / 'packet.json'
                packet(survey)
                adapter = FakeAdapter(**kwargs)
                with self.assertRaisesRegex(ValueError, error):
                    capture(adapter, CASE, survey, root / 'attempt')
                self.assertTrue(adapter.braked and adapter.cleaned)
                self.assertFalse((root / 'attempt').exists())
                self.assertFalse(list(root.glob('attempt.incomplete-*')))

    def test_rebound_canonical_frame_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            mapping = attempt / 'video_frames.jsonl'
            rows = [json.loads(line) for line in mapping.read_text().splitlines()]
            rows[4]['video_frame'] = 5
            mapping.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            acquisition_path = attempt / 'acquisition.json'
            acquisition = json.loads(acquisition_path.read_text())
            acquisition['video_frames.jsonl']['sha256'] = hashlib.sha256(mapping.read_bytes()).hexdigest()
            acquisition_path.write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'canonical original frame identity'):
                measure(attempt)

    def test_rebound_camera_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            mapping = attempt / 'video_frames.jsonl'
            rows = [json.loads(line) for line in mapping.read_text().splitlines()]
            rows[4]['camera_times_s']['approach'] += .02
            mapping.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            acquisition_path = attempt / 'acquisition.json'
            acquisition = json.loads(acquisition_path.read_text())
            acquisition['video_frames.jsonl']['sha256'] = hashlib.sha256(mapping.read_bytes()).hexdigest()
            acquisition_path.write_text(json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, 'four-camera timestamp drift'):
                measure(attempt)

    def test_invalid_image_bytes_never_publish_an_attempt(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            with self.assertRaisesRegex(ValueError, 'decode failed'):
                capture(FakeAdapter(invalid_png=True), CASE, survey, root / 'attempt')
            self.assertFalse((root / 'attempt').exists())
            self.assertFalse(list(root.glob('attempt.incomplete-*')))

    def test_existing_attempt_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            attempt.mkdir()
            sentinel = attempt / 'sentinel'
            sentinel.write_text('original')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                capture(FakeAdapter(), CASE, survey, attempt)
            self.assertEqual(sentinel.read_text(), 'original')

    def test_map_change_during_capture_does_not_publish(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            adapter = FakeAdapter()
            calls = 0

            def changing_map():
                nonlocal calls
                calls += 1
                return ('<OpenDRIVE>surveyed</OpenDRIVE>' if calls == 1
                        else '<OpenDRIVE>changed</OpenDRIVE>')

            adapter.world.map.to_opendrive = changing_map
            with self.assertRaisesRegex(ValueError, 'changed during capture'):
                capture(adapter, CASE, survey, root / 'attempt')
            self.assertFalse((root / 'attempt').exists())

    def test_map_is_sealed_before_adapter_disconnects(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            adapter = FakeAdapter(disconnect_on_cleanup=True)
            capture(adapter, CASE, survey, root / 'attempt')
            self.assertIsNone(adapter.world)
            self.assertEqual((root / 'attempt' / 'road.xodr').read_bytes(),
                             b'<OpenDRIVE>surveyed</OpenDRIVE>')

    def test_survey_context_is_sealed_before_capture_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            original = json.loads(survey.read_text())['context']

            class ChangingPacketAdapter(FakeAdapter):
                def start(self, plan):
                    super().start(plan)
                    changed = json.loads(survey.read_text())
                    changed['context']['camera_plan'] = 'changed after verification'
                    survey.write_text(json.dumps(changed))

            capture(ChangingPacketAdapter(), CASE, survey, root / 'attempt')
            saved = json.loads((root / 'attempt' / 'intersection-context.json').read_text())
            self.assertEqual(saved, original)
            self.assertNotEqual(saved['camera_plan'],
                                json.loads(survey.read_text())['context']['camera_plan'])

    def test_saved_audit_rejects_changed_original_map(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            (attempt / 'road.xodr').write_text('<OpenDRIVE>changed</OpenDRIVE>')
            with self.assertRaisesRegex(ValueError, 'stale original Native source'):
                audit(attempt, CASE, allow_diagnostic=True)

    def test_adapter_cleanup_failure_does_not_publish_partial_capture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            adapter = FakeAdapter(cleanup_failure=True)
            with self.assertRaisesRegex(RuntimeError, 'cleanup failure'):
                capture(adapter, CASE, survey, root / 'attempt')
            self.assertTrue(adapter.braked and adapter.cleaned)
            self.assertFalse((root / 'attempt').exists())
            self.assertFalse(list(root.glob('attempt.incomplete-*')))

    def test_selected_requirement_finalizer_reopens_originals(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            survey = root / 'packet.json'
            packet(survey)
            attempt = root / 'attempt'
            capture(FakeAdapter(), CASE, survey, attempt)
            report = finalize(attempt, CASE)
            self.assertEqual(set(report['measurements']),
                             {'left_turn_observed', 'two_directional_roads',
                              'approach_right_half'})
            self.assertTrue(report['measurements']['approach_right_half']['value']
                            ['all_sampled_body_in_right_half'])
            with self.assertRaisesRegex(ValueError, 'wrong exact saved case'):
                finalize(attempt, CASE + '__wrong')
            (attempt / 'intersection-context.json').unlink()
            with self.assertRaisesRegex(ValueError,
                                        'Missing required source: intersection-context.json'):
                finalize(attempt, CASE)


if __name__ == '__main__':
    unittest.main()

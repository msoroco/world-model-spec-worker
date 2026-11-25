import unittest
import json
import shutil
import tempfile
from unittest import mock

from runner import check
from native_plan import command_from_observation, load_plan, make_controller, survey_governed_sign
from native_capture import CAMERAS, _camera_pose
from saved_native import assess_geometry, check_original_body_join, check_map_source_join, check_capture_seal, SEALED_SOURCES, _decode
from finalize import finalize, _channel
from comparison import assess_pair
from geometry import sampled_source
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


class SourcePreflightTest(unittest.TestCase):
    def test_original_seal_rejects_missing_or_changed_source(self):
        scratch = next(parent for parent in ROOT.parents if parent.name == '.runtime-work')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            for name in SEALED_SOURCES:
                target = attempt / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('sealed source\n')
            import hashlib
            sources = {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                       for name in SEALED_SOURCES}
            seal = {'format': 'worker-sealed-capture', 'provenance_kind': 'native',
                    'diagnostic_fixture': False, 'frames': 600,
                    'restoration': {'restored': True},
                    'events': ['capture_finished', 'encoders_closed',
                               'restoration_verified'],
                    'encoder_exit_codes': {'overview': 0}, 'sources': sources,
                    'native_revision': {'construction_sha256': sources['construction.json'],
                                        'runner_sha256': sources['runner.py']}}
            (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            check_capture_seal(attempt)
            seal['diagnostic_fixture'] = True
            (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            with self.assertRaisesRegex(ValueError, 'capture seal differs'):
                check_capture_seal(attempt)
            seal['diagnostic_fixture'] = False
            (attempt / 'capture-seal.json').write_text(json.dumps(seal) + '\n')
            (attempt / 'native-map.xodr').write_text('changed source\n')
            with self.assertRaisesRegex(ValueError, 'sealed source differs'):
                check_capture_seal(attempt)

    def test_exported_map_is_bound_separately_from_authored_road(self):
        scratch = next(parent for parent in ROOT.parents if parent.name == '.runtime-work')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            (attempt / 'road.xodr').write_text('CARLA exported road')
            (attempt / 'authored-road.xodr').write_text('authored road')
            (attempt / 'native-map.xodr').write_text('CARLA exported road')
            (attempt / 'source.jsonl').write_text('requested route')
            import hashlib
            digest = lambda name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
            config = {'road_sha256': digest('authored-road.xodr'),
                      'source_sha256': digest('source.jsonl')}
            survey = {'native_map_sha256': digest('native-map.xodr')}
            check_map_source_join(attempt, config, survey)
            (attempt / 'native-map.xodr').write_text('changed exported road')
            with self.assertRaisesRegex(ValueError, 'authored/live map'):
                check_map_source_join(attempt, config, survey)
            (attempt / 'native-map.xodr').write_text('CARLA exported road')
            (attempt / 'road.xodr').write_text('changed live road')
            with self.assertRaisesRegex(ValueError, 'authored/live map'):
                check_map_source_join(attempt, config, survey)
            (attempt / 'road.xodr').write_text('CARLA exported road')
            (attempt / 'authored-road.xodr').write_text('changed authored road')
            with self.assertRaisesRegex(ValueError, 'authored/live map'):
                check_map_source_join(attempt, config, survey)

    def test_saved_camera_requires_full_frames_size_and_rate(self):
        scratch = next(parent for parent in ROOT.parents if parent.name == '.runtime-work')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            camera = Path(temporary) / 'overview.mkv'
            camera.write_bytes(b'unit-test-camera')
            stream = {'nb_read_frames': '600', 'width': 1920,
                      'height': 1080, 'r_frame_rate': '20/1'}
            def probe(*_args, **_kwargs):
                return SimpleNamespace(returncode=0,
                                       stdout=json.dumps({'streams': [stream]}))
            with mock.patch('saved_native.subprocess.run', side_effect=probe):
                self.assertEqual(_decode(camera, (1920, 1080))['frames'], 600)
                stream['width'] = 1280
                with self.assertRaisesRegex(ValueError, 'full decode differs'):
                    _decode(camera, (1920, 1080))
                stream['width'] = 1920
                stream['nb_read_frames'] = '599'
                with self.assertRaisesRegex(ValueError, 'full decode differs'):
                    _decode(camera, (1920, 1080))
                stream['nb_read_frames'] = '600'
                stream['r_frame_rate'] = '19/1'
                with self.assertRaisesRegex(ValueError, 'full decode differs'):
                    _decode(camera, (1920, 1080))

    def test_saved_native_binds_actor_trace_and_full_body(self):
        vertices = [[float(i), float(i + 1), 0.5] for i in range(8)]
        native = {'native_center_xy_m': [1.0, 2.0],
                  'native_body_vertices_m': vertices}
        rider = {'actor_id': 7}
        trace = {'position_m': [1.0, 2.0, 0.5]}
        body = {'body_vertices_m': vertices}
        evidence = {'actor_id': 7, 'ego': {'body_vertices_m': vertices,
                                         'position_m': [1.0, 2.0, 0.5]}}
        check_original_body_join(native, rider, trace, body, evidence)
        evidence['actor_id'] = 8
        with self.assertRaisesRegex(ValueError, 'actor identity'):
            check_original_body_join(native, rider, trace, body, evidence)
        evidence['actor_id'] = 7
        trace['position_m'][0] = 2.0
        with self.assertRaisesRegex(ValueError, 'trace position'):
            check_original_body_join(native, rider, trace, body, evidence)
        trace['position_m'][0] = 1.0
        evidence['ego']['position_m'][0] = 2.0
        with self.assertRaisesRegex(ValueError, 'trace position'):
            check_original_body_join(native, rider, trace, body, evidence)
        evidence['ego']['position_m'][0] = 1.0
        body['body_vertices_m'] = [list(vertex) for vertex in vertices]
        body['body_vertices_m'][2][0] = 2.5
        with self.assertRaisesRegex(ValueError, 'body source'):
            check_original_body_join(native, rider, trace, body, evidence)

    def test_saved_finalizer_rebuilds_channels_from_sources(self):
        config, route = load_plan(ROOT)
        scratch = next(parent for parent in ROOT.parents if parent.name == '.runtime-work')
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            shutil.copyfile(ROOT / 'config.json', attempt / 'config.json')
            native = [{'native_frame': i + 50, 'time_s': i / 20,
                       'native_center_xy_m': route[i], 'native_heading_deg': 90,
                       'native_road_id': 1, 'native_lane_id': -1,
                       'native_body_vertices_m': [[0, 0, 0]]} for i in range(600)]
            mapping = [{'video_frame': i, 'native_frame': i + 50,
                        'time_s': i / 20} for i in range(600)]
            rider = [{'frame': i, 'time_s': i / 20, 'actor_id': 7,
                      'machine_class': 'bicycle', 'mounted': None} for i in range(600)]
            trace = [{'frame': i + 50, 'time_s': i / 20,
                      'velocity_mps': [0, 2]} for i in range(600)]
            for name, value in (('native_samples.jsonl', native),
                                ('video_frames.jsonl', mapping),
                                ('rider_native_samples.jsonl', rider),
                                ('trace.jsonl', trace)):
                (attempt / name).write_text(''.join(json.dumps(row) + '\n' for row in value))
            (attempt / 'sign-survey.json').write_text(json.dumps({
                'landmark_id': '11400803' if config['direction'] == 'right' else '11400804',
                'approach_road_id': 1, 'approach_lane_id': -1,
                'landmark_station_m': 56}) + '\n')
            (attempt / 'reference_corner.mkv').write_bytes(b'original-test-camera')
            geometry = {'direction': config['direction'], 'behavior': config['behavior'],
                        'heading_change_deg': 0 if config['behavior'] == 'obey' else 90,
                        'destination_road_id': 2 if config['behavior'] == 'obey' else 3,
                        'engineering_geometry_matched': True}
            review = {'geometry': geometry,
                      'cameras': {name: {} for name in
                                  ('overview', 'approach', 'reference_corner', 'driver_reference')}}
            with mock.patch('finalize.audit_attempt', return_value=review):
                report = finalize(attempt, attempt / 'analysis-report.json')
            self.assertFalse(report['accepted'])
            result = json.loads((attempt / 'result.json').read_text())
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['accepted'])
            self.assertEqual(result['video_references'],
                             ['overview.mkv', 'approach.mkv',
                              'reference_corner.mkv', 'driver_reference.mkv'])
            self.assertEqual(len((attempt / 'channels' / 'drv.turning.jsonl').read_text().splitlines()), 600)
            self.assertEqual(len(result['recording_evidence']),
                             len(config['recording_description']['channels']) + 1)
            with mock.patch('finalize.audit_attempt', return_value=review):
                with self.assertRaisesRegex(ValueError, 'Retain prior saved result'):
                    finalize(attempt, attempt / 'analysis-report.json')

    def test_exact_staged_source(self):
        proof = check()
        self.assertTrue(proof["cpu_source_preflight_passed"])
        self.assertFalse(proof["native_capture_executed"])

    def test_observed_pose_controller_uses_exact_route(self):
        config, route = load_plan(ROOT)
        _, controller = make_controller(ROOT, 1.4, 35)
        first = command_from_observation(controller, route[0], 90, 0)
        self.assertEqual(first['observed_native_xy_m'], route[0])
        self.assertLess(first['route_error_m'], .01)
        if config['behavior'] == 'turn':
            # At turn release, the two signed directions require opposite steering.
            for point in route[1:220]:
                command_from_observation(controller, point, 90, 2)
            at_turn = command_from_observation(controller, route[220], 90, 2)
            self.assertLess(at_turn['steer'], 0) if config['direction'] == 'right' else self.assertGreater(at_turn['steer'], 0)
        with self.assertRaisesRegex(ValueError, 'departed'):
            command_from_observation(controller, [60, 60], 90, 2)

    def test_live_map_survey_rejects_wrong_sign_or_lane(self):
        config, _ = load_plan(ROOT)
        sign_id = '11400803' if config['direction'] == 'right' else '11400804'
        lane = SimpleNamespace(road_id=1, lane_id=-1, lane_width=3.5,
                               transform=SimpleNamespace(get_forward_vector=lambda:
                                   SimpleNamespace(x=0, y=1)))
        class Map:
            def get_waypoint(self, *_args, **_kwargs):
                return lane
            def get_all_landmarks(self):
                return [SimpleNamespace(id=sign_id, road_id=1, s=56)]
        carla = SimpleNamespace(Location=lambda **kwargs: kwargs,
                                LaneType=SimpleNamespace(Driving='driving'))
        survey = survey_governed_sign(Map(), carla, config)
        self.assertEqual(survey['landmark_id'], sign_id)
        self.assertEqual(survey['official_device_authorization'], 'unreviewed')
        lane.lane_id = 1
        with self.assertRaisesRegex(ValueError, 'lane readback'):
            survey_governed_sign(Map(), carla, config)
        lane.lane_id = -1
        class WrongSign(Map):
            def get_all_landmarks(self):
                return [SimpleNamespace(id='other', road_id=1, s=56)]
        with self.assertRaisesRegex(ValueError, 'landmark readback'):
            survey_governed_sign(WrongSign(), carla, config)

    def test_capture_camera_contract_is_lazy_and_four_view(self):
        self.assertEqual([row[0] for row in CAMERAS],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual([(row[1], row[2]) for row in CAMERAS],
                         [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)])
        fake = SimpleNamespace(Location=lambda **kw: SimpleNamespace(**kw),
                               Rotation=lambda **kw: SimpleNamespace(**kw),
                               Transform=lambda loc, rot: SimpleNamespace(location=loc, rotation=rot))
        pose = _camera_pose(fake, CAMERAS[0][3], CAMERAS[0][4])
        self.assertLess(pose.rotation.pitch, 0)
        ego_pose = _camera_pose(fake, CAMERAS[3][3], None)
        self.assertEqual(ego_pose.location.x, 1)

    def test_saved_geometry_requires_observed_destination_and_turn(self):
        config, route = load_plan(ROOT)
        direction, behavior = config['direction'], config['behavior']
        exit_road = 2 if behavior == 'obey' else (3 if direction == 'right' else 4)
        exit_heading = 90 if behavior == 'obey' else (0 if direction == 'right' else 180)
        native = [{'native_heading_deg': 90 if i < 300 else exit_heading,
                   'native_center_xy_m': route[i],
                   'native_road_id': 1 if i < 310 else exit_road} for i in range(600)]
        measured = assess_geometry(native, config)
        self.assertTrue(measured['engineering_geometry_matched'])
        self.assertFalse(measured['official_sign_authorization_verified'])
        if direction == 'left' and behavior == 'turn':
            for index, row in enumerate(native[550:570]):
                row['native_heading_deg'] = 179 if index % 2 else -179
            self.assertTrue(assess_geometry(native, config)['engineering_geometry_matched'])
            for row in native[550:570]:
                row['native_heading_deg'] = exit_heading
        native[550]['native_road_id'] = 9
        with self.assertRaisesRegex(ValueError, 'destination road'):
            assess_geometry(native, config)
        native[550]['native_road_id'] = exit_road
        for row in native[550:570]:
            row['native_heading_deg'] = -90
        with self.assertRaisesRegex(ValueError, 'signed-turn geometry'):
            assess_geometry(native, config)

    def test_controlled_pair_checks_original_approach(self):
        config, _ = load_plan(ROOT)
        direction = config['direction']
        def source(behavior):
            rows = sampled_source(direction, behavior)
            exit_road = 2 if behavior == 'obey' else (3 if direction == 'right' else 4)
            exit_heading = 90 if behavior == 'obey' else (0 if direction == 'right' else 180)
            return [{'native_heading_deg': 90 if i < 300 else exit_heading,
                     'native_center_xy_m': row['body_center_xy_m'],
                     'native_road_id': 1 if i < 310 else exit_road}
                    for i, row in enumerate(rows)]
        obey, turn = source('obey'), source('turn')
        obey_config = {**config, 'behavior': 'obey'}
        turn_config = {**config, 'behavior': 'turn'}
        survey = {'landmark_id': '11400803' if direction == 'right' else '11400804'}
        result = assess_pair(obey, turn, obey_config, turn_config, survey, survey)
        self.assertEqual(result['fixed_approach_frames'], 221)
        turn[100]['native_center_xy_m'] = [2, -30]
        with self.assertRaisesRegex(ValueError, 'observed approach'):
            assess_pair(obey, turn, obey_config, turn_config, survey, survey)

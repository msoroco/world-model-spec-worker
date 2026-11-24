"""Materialize six unselected exact Native sweep constructions for CPU checks."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'draft-primary/reference/primary/construction.json'
OUT = HERE / 'sweep-cases'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Native source anchor differs: ' + old[:80])
    return text.replace(old, new)


def build_runner(source, cases):
    start = source.index('def check(config):')
    end = source.index('def phase_at(config, frame):')
    checks = '''def check(config):
    case_id = config.get('case_id')
    allowed = SWEEP_CASES
    if case_id not in allowed or config.get('selected_case_id') != case_id:
        raise ValueError('Exact sweep case identity differs')
    if (config.get('law_id') != 'LVMC-11-16-090-A'
            or config.get('cell_id') != 'C229597'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('candidate_id') != 'primary'
            or config.get('spawn_point_index') != 0
            or config.get('duration_s') != 30 or config.get('rate_hz') != 20
            or config.get('vehicle_blueprint') != 'vehicle.tesla.model3'):
        raise ValueError('Sweep vehicle or duration contract differs')
    expected_kind, expected_target = allowed[case_id]
    if config.get('sweep_kind') != expected_kind or config.get('sweep_target') != expected_target:
        raise ValueError('Frozen physical sweep target differs')
    if expected_kind == 'acceleration':
        require_target(expected_target, ACCEL_TARGETS_MPS2, 'Acceleration target')
    else:
        require_target(expected_target, ROUTE_OFFSETS_M, 'Route offset')
    phases = config.get('control_phases', [])
    expected = [(0, 159, 0.28), (160, 319, 0.75),
                (320, 439, 0.92), (440, 599, 0.2)]
    if [(p.get('first_frame'), p.get('last_frame'), p.get('throttle'))
            for p in phases] != expected:
        raise ValueError('Sweep control phases differ')
    cameras = config.get('cameras', [])
    if ([c.get('name') for c in cameras] != list(VIEWS)
            or any(c.get('width') != (1920 if c['name'] == 'overview' else 1280)
                   or c.get('height') != (1080 if c['name'] == 'overview' else 720)
                   for c in cameras)):
        raise ValueError('Four synchronized source cameras required')
    return {'case_id': case_id, 'candidate_id': 'primary',
            'sweep_kind': expected_kind, 'requested_target': expected_target,
            'frames': FRAMES, 'rate_hz': HZ, 'camera_views': list(VIEWS),
            'carla_contacted': False, 'physical_response_verified': False,
            'highway_status_verified': False, 'legal_verdict_claimed': False}


'''
    source = source[:start] + checks + source[end:]
    helper = (HERE / 'sweep_native.py').read_text()
    marker = "FRAMES = 600\nHZ = 20\n"
    source = replace_once(source, marker,
                          marker + '\nSWEEP_CASES = ' + repr(cases) + '\n' + helper + '\n')
    source = replace_once(source,
                          "ego = world.try_spawn_actor(blueprint, spawn[config['spawn_point_index']])",
                          "spawn_transform = spawn[config['spawn_point_index']]\n"
                          "        if config['sweep_kind'] == 'route':\n"
                          "            spawn_transform = route_waypoint(world.get_map(), spawn_transform,\n"
                          "                                              config['sweep_target']).transform\n"
                          "        ego = world.try_spawn_actor(blueprint, spawn_transform)")
    source = replace_once(source, 'for index in range(FRAMES):',
                          'prior_throttle = 0.0\n            for index in range(FRAMES):')
    source = replace_once(source,
                          "ego.apply_control(carla.VehicleControl(throttle=phase['throttle'],",
                          "requested_throttle = phase['throttle']\n"
                          "                if config['sweep_kind'] == 'acceleration' and 160 <= index <= 439:\n"
                          "                    measured_acceleration = longitudinal_acceleration(\n"
                          "                        ego.get_acceleration(), ego.get_transform().rotation.yaw)\n"
                          "                    requested_throttle = throttle_for_acceleration(\n"
                          "                        config['sweep_target'], measured_acceleration, prior_throttle)\n"
                          "                prior_throttle = requested_throttle\n"
                          "                ego.apply_control(carla.VehicleControl(throttle=requested_throttle,")
    source = replace_once(source,
                          "capture.capture(frame_id, index / HZ,\n                                extra={'video_frame': index,",
                          "route_projection = world.get_map().get_waypoint(ego.get_transform().location)\n"
                          "                if route_projection is None:\n"
                          "                    raise RuntimeError('Original route projection unavailable')\n"
                          "                capture.capture(frame_id, index / HZ,\n"
                          "                                extra={'route_position_m': route_projection.s,\n"
                          "                                       'route_road_id': route_projection.road_id,\n"
                          "                                       'route_section_id': route_projection.section_id,\n"
                          "                                       'route_lane_id': route_projection.lane_id,\n"
                          "                                       'video_frame': index,")
    return source


def build_finalizer(source):
    source = replace_once(source,
                          "    speeds = []\n    accelerations = []",
                          "    speeds = []\n    accelerations = []\n    route_positions = []\n    road_ids = set()")
    source = replace_once(source,
                          "        speeds.append(math.sqrt(sum(v*v for v in velocity)))",
                          "        route_position = motion.get('route_position_m')\n"
                          "        road_id = motion.get('route_road_id')\n"
                          "        if (type(route_position) not in (int, float)\n"
                          "                or not math.isfinite(route_position) or type(road_id) is not int):\n"
                          "            raise ValueError('Missing original route projection at ' + str(index))\n"
                          "        route_positions.append(route_position)\n"
                          "        road_ids.add(road_id)\n"
                          "        speeds.append(math.sqrt(sum(v*v for v in velocity)))")
    source = replace_once(source,
                          "        accelerations.append(math.sqrt(sum(a*a for a in acceleration)))",
                          "        heading = motion.get('heading_deg')\n"
                          "        if type(heading) not in (int, float) or not math.isfinite(heading):\n"
                          "            raise ValueError('Missing original heading at ' + str(index))\n"
                          "        radians = math.radians(heading)\n"
                          "        accelerations.append(acceleration[0] * math.cos(radians)\n"
                          "                             + acceleration[1] * math.sin(radians))")
    source = replace_once(source,
                          "    return {'frames': FRAMES, 'first_time_s': 0.0,",
                          "    if len(road_ids) != 1:\n"
                          "        raise ValueError('Original route changed road identity')\n"
                          "    return {'frames': FRAMES, 'first_time_s': 0.0,")
    source = replace_once(source,
                          "            'acceleration_series_mps2': accelerations}",
                          "            'acceleration_series_mps2': accelerations,\n"
                          "            'route_position_series_m': route_positions,\n"
                          "            'route_road_ids': sorted(road_ids)}")
    source = replace_once(source,
                          "    pose_channel = channel_dir / 'ego_pose.jsonl'",
                          "    route_channel = channel_dir / 'route_position_m.jsonl'\n"
                          "    route_channel.write_text(''.join(json.dumps({'time_s': i / HZ, 'value': value}) + '\\n'\n"
                          "                                     for i, value in enumerate(measurement['route_position_series_m'])))\n"
                          "    pose_channel = channel_dir / 'ego_pose.jsonl'")
    source = replace_once(source,
                          "               if not key.endswith('_series_mps') and not key.endswith('_series_mps2')}",
                          "               if not key.endswith('_series_mps') and not key.endswith('_series_mps2')\n"
                          "               and not key.endswith('_series_m')}")
    source = replace_once(source,
                          "                               {'name': 'ego_pose', 'unit': 'structured',",
                          "                               {'name': 'route_position_m', 'unit': 'm',\n"
                          "                                'reference': 'channels/route_position_m.jsonl'},\n"
                          "                               {'name': 'ego_pose', 'unit': 'structured',")
    source = replace_once(source,
                          "    report = {'format': 'c229597-source-motion-analysis-v1',",
                          "    if config['sweep_kind'] == 'acceleration':\n"
                          "        sweep_summary = {'ego_acceleration': {\n"
                          "            'value': max(measurement['acceleration_series_mps2'][160:440]),\n"
                          "            'unit': 'm/s2',\n"
                          "            'method': 'original Native longitudinal acceleration vector',\n"
                          "            'time_window': 'frames 160 through 439, excluding startup',\n"
                          "            'statistic': 'max', 'sample_window_s': [8.0, 21.95],\n"
                          "            'reference': 'channels/acceleration_mps2.jsonl'}}\n"
                          "    else:\n"
                          "        sweep_summary = {'route_position_m': {\n"
                          "            'value': measurement['route_position_series_m'][0],\n"
                          "            'unit': 'm',\n"
                          "            'method': 'original vehicle pose joined to source-hashed road geometry',\n"
                          "            'time_window': 'all 600 original frames',\n"
                          "            'statistic': 'first', 'sample_window_s': [0.0, 29.95],\n"
                          "            'reference': 'channels/route_position_m.jsonl'}}\n"
                          "    report = {'format': 'c229597-source-motion-analysis-v1',")
    source = replace_once(source,
                          "        'realized_observables': {},",
                          "        'realized_observables': sweep_summary,")
    return source


def test_source():
    return '''import json
import unittest
from pathlib import Path
import runner


class SweepConstructionTest(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(Path('config.json').read_text())

    def test_exact_cpu_check(self):
        result = runner.check(self.config)
        self.assertEqual(result['case_id'], self.config['case_id'])
        self.assertFalse(result['carla_contacted'])
        self.assertFalse(result['physical_response_verified'])

    def test_source_interval(self):
        self.assertEqual(runner.phase_at(self.config, 0)['name'], 'approach')
        self.assertEqual(runner.phase_at(self.config, 599)['name'], 'departure')
        with self.assertRaises(ValueError):
            runner.phase_at(self.config, 600)

    def test_changed_target_rejected(self):
        self.config['sweep_target'] = -1
        with self.assertRaises(ValueError):
            runner.check(self.config)
'''


def main():
    stage = json.loads((HERE / 'proposals/cases.json').read_text())
    sweeps = [c for c in stage['cases'] if c['target_type'] == 'judgment_sweep']
    if len(sweeps) != 6:
        raise ValueError('Expected exactly six expanded judgment cases')
    targets = {c['case_id']: ('acceleration' if c['sweep_id'].endswith('-1') else 'route',
                              next(iter(c['sweep_point'].values()))) for c in sweeps}
    source = json.loads(SOURCE.read_text())
    files = {f['path']: f['content'] for f in source['files']}
    runner = build_runner(files['runner.py'], targets)
    finalizer = build_finalizer(files['measure_episode.py'])
    entries = []
    for case in sweeps:
        construction = copy.deepcopy(source)
        construction['case_id'] = case['case_id']
        construction['status'] = 'unselected_canonical_sweep_construction'
        construction['measurement_plan'] = ('Record actual original Native acceleration and route position; '
            'controller targets are engineering requests; both legal judgments remain unknown.')
        construction['recording_description'] = case['recording_description']
        construction['mechanisms'].append('Source-planned physical sweep target with original response measured separately')
        for file in construction['files']:
            if file['path'] == 'runner.py':
                file['content'] = runner
            elif file['path'] == 'measure_episode.py':
                file['content'] = finalizer
            elif file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['case_id'] = case['case_id']
                config['selected_case_id'] = case['case_id']
                config['case'] = {'case_id': case['case_id'], 'name': 'reference'}
                config['supported_case_ids'] = list(targets)
                config['sweep_kind'], config['sweep_target'] = targets[case['case_id']]
                file['content'] = json.dumps(config, indent=2) + '\n'
            elif file['path'] == 'tests/test_offline.py':
                file['content'] = test_source()
        folder = OUT / case['case_id']
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': case['case_id'], 'sweep_id': case['sweep_id'],
                        'sweep_target': targets[case['case_id']][1],
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path)})
    index = {'format': 'c229597-unselected-canonical-sweep-constructions-v1',
             'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json'),
             'source_construction_sha256': sha(SOURCE),
             'entries': entries, 'selected': False, 'native_executed': False,
             'legal_verdict_claimed': False, 'delivery_ready': False}
    path = OUT / 'index.json'
    path.write_text(json.dumps(index, indent=2) + '\n')
    original_manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    offline_manifest = {
        'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': original_manifest['runtime_manifest_sha256'],
        'status': 'unselected_canonical_sweep_cpu_construction',
        'cases': [{'case_id': row['case_id'], 'kind': 'draft_not_selected',
                   'construction': str((HERE / row['construction']).relative_to(OUT)),
                   'construction_sha256': row['construction_sha256'],
                   'candidates': []} for row in entries]}
    manifest_path = OUT / 'manifest.json'
    manifest_path.write_text(json.dumps(offline_manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(entries), 'index_sha256': sha(path)}))


if __name__ == '__main__':
    main()

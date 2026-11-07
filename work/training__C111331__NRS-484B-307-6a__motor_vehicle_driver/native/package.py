"""Build the eight exact unselected C111331 CPU construction bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AID = HERE.parent.name
CASES = ('reference', 'contrast')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
TEST = '''import copy
import json
from pathlib import Path
import unittest
import runner
from types import SimpleNamespace

class ExactRequestTests(unittest.TestCase):
    def test_exact_request(self):
        result = runner.check()
        self.assertTrue(result['passed'])
        self.assertEqual(result['request_rows'], 480)
        self.assertFalse(result['carla_imported'])
        self.assertFalse(result['physical_success_claimed'])

    def test_request_corruption_rejected(self):
        path = Path('native-requests.jsonl')
        original = path.read_text()
        try:
            rows = [json.loads(line) for line in original.splitlines()]
            rows[200]['signal_phase_requested'] = 'green'
            path.write_text(''.join(json.dumps(row) + '\\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                runner.check()
        finally:
            path.write_text(original)

    def test_observation_claim_rejected(self):
        path = Path('config.json')
        original = path.read_text()
        try:
            config = json.loads(original)
            config['no_native_or_original_observation_claimed'] = False
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'Physical evidence claimed'):
                runner.check()
        finally:
            path.write_text(original)

    def test_observed_tick_saved_handoff(self):
        sample = {'request_index': 7, 'native_frame': 107, 'time_s': .35,
                  'native_center_xy_m': [1.75, -8.5], 'native_z_m': .5,
                  'native_body_xy_m': [[1, -9], [2, -9], [2, -8], [1, -8]],
                  'native_yaw_deg': 90, 'speed_mps': 4.0}
        native, trace, video = runner.saved_capture_rows(sample, 7)
        self.assertEqual(native['source_kind'], 'original_native_observation')
        self.assertEqual(trace['frame'], video['native_frame'])
        self.assertEqual(trace['frame'], video['carla_frame'])
        self.assertEqual(trace['position_m'], [1.75, -8.5, .5])
        self.assertNotIn('source_kind', sample)
        with self.assertRaisesRegex(ValueError, 'frame or body differs'):
            runner.saved_capture_rows(sample, 8)

    def test_signal_camera_uses_authored_geometry(self):
        config = json.loads(Path('config.json').read_text())
        camera = runner.signal_camera_plan(config)
        self.assertEqual([camera['x'], camera['y']], config['camera_plan']['authored_xy_m'])
        self.assertGreater(camera['yaw_deg'], 0)
        self.assertLess(camera['yaw_deg'], 90)
        self.assertEqual(camera['horizontal_fov_deg'], config['camera_plan']['horizontal_fov_deg'])

    def test_four_original_camera_sources(self):
        config = json.loads(Path('config.json').read_text())
        plans = runner.original_camera_plans(config)
        self.assertEqual(set(plans), {'overview', 'approach', 'reference_corner', 'driver_reference'})
        self.assertEqual(plans['overview']['size'], (1920, 1080))
        self.assertTrue(all(plan['size'] == (1280, 720) for name, plan in plans.items() if name != 'overview'))
        self.assertEqual(plans['reference_corner']['fov_deg'], config['camera_plan']['horizontal_fov_deg'])
        self.assertEqual(plans['reference_corner']['y'], config['camera_plan']['authored_xy_m'][1])
        self.assertTrue(plans['driver_reference']['attach_to_ego'])

    def test_observed_speed_uses_current_tick_and_rejects_nonfinite(self):
        class Actor:
            speed = 2.0
            def get_velocity(self):
                return SimpleNamespace(x=self.speed, y=0.0)
        actor = Actor()
        before = runner.observed_speed_mps(actor)
        actor.speed = .25
        self.assertEqual(before, 2.0)
        self.assertEqual(runner.observed_speed_mps(actor), .25)
        actor.speed = float('nan')
        with self.assertRaisesRegex(RuntimeError, 'nonfinite'):
            runner.observed_speed_mps(actor)

if __name__ == '__main__': unittest.main()
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    summary = json.loads((HERE / 'request-summary.json').read_text())
    assert summary['assignment_id'] == AID and len(summary['cases']) == 8
    batch = json.loads((REPO / 'batch.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'source_branch': 'yellow_warning_red_entry', 'cases': []}
    fixed_files = [{'path': name, 'content': (HERE / name).read_text()}
                   for name in ('runner.py', 'road.xodr', 'measure_saved.py',
                                'signal_video_cpu.py', 'finalize.py')]
    fixed_files.append({'path': 'tests/test_construction.py', 'content': TEST})
    for case in CASES:
        case_id = AID + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected', 'candidates': [],
                 'measurement_contract': f'measurement-contracts/{case}.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c111331-saved-signal-entry-report-v1'},
                 'candidate_risk': {'status': 'native_and_original_pixels_unverified',
                                    'reason': 'Requested signal phase and junction entry require observed Native actor and pixel evidence'}}
        write(HERE / 'measurement-contracts' / (case + '.json'), {
            'format': 'worker-measurement-contract-v1', 'case_id': case_id,
            'requirements': [
                {'disposition_index': index, 'requirement': requirement,
                 'source': 'inputs/coverage/branch-sources.json',
                 'output_key': key, 'method': method, 'value_type': value_type,
                 'kind': 'measured', 'inputs': ['native_samples.jsonl',
                     'video_frames.jsonl', 'signal_reference.mkv']}
                for index, requirement, key, method, value_type in (
                    (0, 'text-0', 'yellow_warning_onset_frame', 'measure_yellow_onset', 'number'),
                    (1, 'text-1', 'observed_signal_phase_at_entry', 'measure_phase_at_entry', 'text'),
                    (2, 'reviewed-scope-0', 'red_exhibition_onset_frame', 'measure_red_onset', 'number'),
                    (3, 'reviewed-scope-1', 'full_body_intersection_entry_frame', 'measure_body_entry', 'number'),
                    (4, 'reviewed-scope-2', 'entry_to_red_margin_frames', 'measure_entry_red_margin', 'number'))],
            'negative': {'remove': ['native_samples.jsonl'],
                         'error_contains': 'Missing required source: native_samples.jsonl'},
            'uncertainty': {'frame_bracket_s': .05,
                            'original_pixel_visibility': 'requires later GPU capture and review'}})
        for candidate in CANDIDATES:
            folder = HERE / 'drafts' / case / candidate
            authored = json.loads((folder / 'config.json').read_text())
            request = folder / 'native-requests.jsonl'
            assert authored['case_id'] == case_id and authored['candidate_id'] == candidate
            config = dict(authored)
            config.update({'case_suffix': case, 'cell_id': 'C111331', 'law_id': 'NRS-484B-307-6a',
                           'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 24,
                           'native_requests_sha256': sha(request),
                           'authored_config_sha256': sha(folder / 'config.json'),
                           'physical_success_claimed': False})
            files = fixed_files + [
                {'path': 'native-requests.jsonl', 'content': request.read_text()},
                {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
            construction = {'case_id': case_id, 'cell_id': 'C111331',
                            'law_id': 'NRS-484B-307-6a', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'recording_description': {'channels': [
                                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                                 'method': 'original Native frame join', 'time_window': '480 frames',
                                 'reference_frame': 'Native imported OpenDRIVE', 'uncertainty': '50 ms frame bracket'}
                                for name in ('native_body_pose', 'observed_signal_state', 'signal_camera_frame_join')],
                                'context_inputs': [
                                    {'name': 'authored_road', 'unit': 'structured',
                                     'method': 'source-hashed OpenDRIVE road.xodr'},
                                    {'name': 'authored_signal_request', 'unit': 'structured',
                                     'method': 'source-hashed native-requests.jsonl'}],
                                'limitations': ['Native signal behavior and original pixels unverified']},
                            'static_checks': ['480 frame request identity', 'OpenDRIVE signal ID and source hashes',
                                              'requested phase and body entry recomputation'],
                            'termination_rules': ['retain capture and restoration error', 'require 480 synchronized frames'],
                            'mechanisms': ['same-cell yellow/red controlled pair', 'observed-pose actor control',
                                           'lossless signal reference camera'],
                            'status': 'unselected_cpu_draft'}
            relative = f'package-candidates/{case}/{candidate}/construction.json'
            target = HERE / relative
            write(target, construction)
            ref = {'id': candidate, 'construction': relative, 'construction_sha256': sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = authored['measured_trigger']
                ref['changed_knobs'] = {'fallback1': ['reference_red_frame', 'contrast_red_frame'],
                                        'fallback2': ['speed_m_per_frame'],
                                        'fallback3': ['signal_camera_fov_deg']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(HERE / 'package-manifest.json', manifest)
    proposals = {'cell_id': 'C111331', 'actor': 'motor_vehicle_driver',
                 'status': 'unselected_cpu_draft', 'cases': []}
    for entry in manifest['cases']:
        construction = json.loads((HERE / entry['construction']).read_text())
        proposals['cases'].append({
            'case_id': entry['case_id'], 'target_law_id': 'NRS-484B-307-6a',
            'target_type': 'attempt',
            'recording_description': construction['recording_description']})
    write(HERE / 'proposals/cases.json', proposals)
    return {'case_count': len(CASES), 'candidate_count': 8,
            'manifest_sha256': sha(HERE / 'package-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))

"""Build eight exact source-gated red-left diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720, 'fov_deg': 75,
            'pose_strategy': 'reviewed signal, stop reference and conflict zone'} for name in NAMES]
CHANNELS = [
    {'name': name, 'method': method, 'unit': unit,
     'reference_frame': 'source-sealed original Native frame map',
     'sampling_rate_hz': 20, 'time_window': 'full 45-second episode',
     'uncertainty': 'physical realization and legal classification remain unresolved'}
    for name, method, unit in (
        ('signal_red_alone', 'official signal actor original state', 'source record'),
        ('stop_reference', 'reviewed crosswalk/marking/intersection hierarchy', 'source record'),
        ('pre_entry_stop', 'original full-body front and speed', 'source record'),
        ('approach_lane', 'reviewed one-way lane and original ego lane', 'source record'),
        ('receiving_direction', 'reviewed route direction', 'source record'),
        ('directed_conflict', 'original pedestrian and traffic conflict frames', 'source record'))]
RECORDING = {'channels': CHANNELS,
             'context_inputs': [{'name': 'reviewed_red_left_site_packet',
                                 'method': 'source-hashed OpenDRIVE, official signal, route and stop reference',
                                 'unit': 'source record'}],
             'limitations': ['No reviewed C153046 site packet is in frozen input.',
                             'Requested controller action is not original physical completion.']}
TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case_capture_profile(self):
        config = check(Path(__file__).resolve().parents[1])
        self.assertEqual(config['rate_hz'], 20)
        self.assertEqual(config['frame_count'], 900)
        self.assertEqual(len(config['cameras']), 4)

if __name__ == '__main__':
    unittest.main()
'''


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    entries = []
    for row in plan['cases']:
        case = row['case_id']
        suffix = case.removeprefix(ROOT.name + '__')
        config = {'assignment_id': ROOT.name, 'law_id': plan['law_id'],
                  'cell_id': plan['cell_id'], 'actor': plan['actor'],
                  'selected_case_id': case,
                  'supported_case_ids': sorted(item['case_id'] for item in plan['cases']),
                  'case': {'case_id': case, 'draft_variables': row['draft_variables'],
                           'recording_description': RECORDING},
                  'plan_sha256': hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                  'rate_hz': 20, 'frame_count': 900, 'duration_s': 45,
                  'control': {'approach_hold_margin_m': 1.0},
                  'cameras': CAMERAS, 'required_atoms': [], 'source_packets': [],
                  'diagnostic_only': True, 'recording_description': RECORDING}
        files = [{'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True) + '\n'},
                 {'path': 'case-plan.json', 'content': plan_path.read_text(),
                  'source': f'work/{ROOT.name}/case-plan.json'},
                 {'path': 'tests/test_bundle.py', 'content': TEST}]
        for name in ('runner.py', 'analysis.py', 'native_capture.py', 'native_setup.py',
                     'red_left_controller.py', 'red_left_measurement.py', 'comparison_audit.py',
                     'delivery_audit.py'):
            files.append({'path': name, 'content': (ROOT / name).read_text(),
                          'source': f'work/{ROOT.name}/{name}'})
        construction = {'case_id': case, 'cell_id': plan['cell_id'],
                        'law_id': plan['law_id'], 'actor': plan['actor'],
                        'candidate_id': 'primary', 'entrypoint': 'runner.py',
                        'files': files, 'recording_description': RECORDING,
                        'measurement_plan': {'case_id': case, 'original_frames': 900,
                                             'procedure': 'red_left_measurement.py',
                                             'legal_judgment': 'unresolved',
                                             'source_packets': ['reviewed_red_left_site_packet',
                                                                'history', 'frame_map', 'four_camera_png']},
                        'static_checks': ['exact law/cell/case identity',
                                          'reviewed official red signal and stop hierarchy',
                                          '20 Hz original-frame four-camera joins'],
                        'termination_rules': ['900 original frames at 20 Hz',
                                              'fail closed on absent original site or signal'],
                        'mechanisms': ['reviewed Native site packet',
                                       'exact one-way left-turn controller',
                                       'source-sealed four-camera original capture']}
        relative = f'cases/{suffix}/construction.json'
        digest = write(ROOT / relative, construction)
        (ROOT / f'cases/{suffix}/config.json').write_text(files[0]['content'])
        # build_diagnostic.py owns the canonical, source-inventoried fixture recipe.
        disposition = plan['requirement_dispositions'][0]
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': disposition['requirement'],
                                      'source': disposition['source'],
                                      'kind': 'measured', 'method': 'build',
                                      'value_type': 'object',
                                      'output_key': 'red_left_motion',
                                      'inputs': ['original-attempt/history.jsonl',
                                                 'original-attempt/frame-map.json',
                                                 'original-attempt/site-packet.json']}],
                    'negative': {'remove': ['original-attempt/site-packet.json'],
                                 'error_contains': 'Missing required source: original-attempt/site-packet.json'}}
        write(ROOT / f'measurement-{suffix}.json', contract)
        fallback_config = dict(config, control={'approach_hold_margin_m': 2.0})
        fallback_files = [dict(item, content=json.dumps(fallback_config, indent=2,
                          sort_keys=True) + '\n') if item['path'] == 'config.json'
                          else item for item in files]
        fallback = dict(construction, candidate_id='fallback1', files=fallback_files)
        fallback_path = f'cases/{suffix}/fallback1/construction.json'
        fallback_sha = write(ROOT / fallback_path, fallback)
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': relative, 'construction_sha256': digest,
                        'diagnostic_only': True,
                        'fixture_recipe': f'work/{ROOT.name}/diagnostic-{suffix}-recipe.json',
                        'measurement_contract': f'measurement-{suffix}.json',
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'candidate_risk': {'status': 'physical',
                            'reason': 'Original ego may overshoot the reviewed stop reference; an earlier body-front hold trigger is tested.'},
                        'candidates': [{'id': 'fallback1', 'construction': fallback_path,
                                        'construction_sha256': fallback_sha,
                                        'trigger': {'source': 'original Native history',
                                                    'metric': 'body-front position at first zero-speed frame',
                                                    'failure_condition': 'first zero-speed frame crosses reviewed stop reference'},
                                        'changed_knobs': ['approach_hold_margin_m: 1.0 to 2.0']}],
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'}})
    write(ROOT / 'execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
        'runtime_manifest_sha256': hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'diagnostic_only': True, 'cases': entries})
    print('built source-gated diagnostic constructions:', len(entries))


if __name__ == '__main__':
    main()

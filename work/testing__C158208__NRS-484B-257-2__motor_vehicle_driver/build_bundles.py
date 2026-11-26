"""Materialize four exact source-gated non-through yield constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if name == 'overview' else 1280,
            'height': 1080 if name == 'overview' else 720, 'fov_deg': 75,
            'pose_strategy': 'reviewed yield sign, physical entry and other participant'}
           for name in NAMES]
CHANNELS = [
    {'name': name, 'method': method, 'unit': unit,
     'reference_frame': 'source-sealed original Native frame map',
     'sampling_rate_hz': 20, 'time_window': 'full 45-second episode',
     'uncertainty': 'physical realization and legal judgment remain unresolved'}
    for name, method, unit in (
        ('non_through_classification', 'reviewed map and entrance inventory', 'source record'),
        ('entrance_controls', 'reviewed all-entrance device inventory', 'source record'),
        ('yield_sign', 'reviewed ego-facing official yield device', 'source record'),
        ('stop_reference', 'reviewed subsection 1 stop-reference hierarchy', 'm'),
        ('ego_speed', 'original Native velocity magnitude', 'm/s'),
        ('ego_body_position', 'original body vertices and leading station', 'm'),
        ('other_body_position', 'original center and minimum body vertex station', 'm'),
        ('other_obligation', 'reviewed other-entrance control', 'source record'),
        ('other_phase', 'original within/approaching phase history', 'source record'),
        ('sightlines', 'original eye-to-conflict sightline history', 'source record'),
        ('officer_signal_control', 'reviewed exception controls and original state', 'source record'),
        ('across_or_within', 'original body-overlap/clearance history', 'source record'))]
RECORDING = {'channels': CHANNELS,
             'context_inputs': [{'name': 'reviewed_nonthrough_yield_site_packet',
                                 'method': 'source-hashed OpenDRIVE, signs, routes and obligations',
                                 'unit': 'source record'}],
             'limitations': ['No reviewed C158208 original site packet is in frozen input.',
                             'Requested response and station are not physical measurements.']}
TEST = '''import json
import unittest
from pathlib import Path
from runner import check

class BundleTests(unittest.TestCase):
    def test_exact_case_capture(self):
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
    for row in (item for item in plan['cases']
                if item.get('target_type') != 'crossing_speed_judgment_sweep_attempt'):
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
        for name in ('runner.py', 'analysis.py', 'native_capture.py', 'yield_site.py',
                     'nonthrough_yield.py', 'delivery_audit.py',
                     'selected_delivery.py', 'comparison_audit.py'):
            files.append({'path': name, 'content': (ROOT / name).read_text(),
                          'source': f'work/{ROOT.name}/{name}'})
        construction = {'case_id': case, 'cell_id': plan['cell_id'],
                        'law_id': plan['law_id'], 'actor': plan['actor'],
                        'candidate_id': 'primary', 'entrypoint': 'runner.py',
                        'files': files, 'recording_description': RECORDING,
                        'measurement_plan': {'case_id': case, 'original_frames': 900,
                                             'procedure': 'analysis.py',
                                             'legal_judgment': 'unresolved',
                                             'source_packets': ['reviewed_nonthrough_yield_site_packet',
                                                                'history', 'frame_map', 'four_camera_png']},
                        'static_checks': ['exact law/cell/case identity',
                                          'reviewed non-through and all-entrance controls',
                                          '20 Hz original four-camera/frame joins'],
                        'termination_rules': ['900 original frames at 20 Hz',
                                              'fail closed on absent reviewed site'],
                        'mechanisms': ['reviewed Native non-through intersection',
                                       'yield approach with non-obligated participant',
                                       'source-sealed four-camera original capture']}
        relative = f'cases/{suffix}/construction.json'
        digest = write(ROOT / relative, construction)
        (ROOT / f'cases/{suffix}/config.json').write_text(files[0]['content'])
        disposition = plan['requirement_dispositions'][0]
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0,
                                      'requirement': disposition['requirement'],
                                      'source': disposition['source'],
                                      'kind': 'measured', 'method': 'build',
                                      'value_type': 'object',
                                      'output_key': 'nonthrough_yield_motion',
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
                            'reason': 'Original ego may overshoot the reviewed yield reference; an earlier body-front hold trigger is tested.'},
                        'candidates': [{'id': 'fallback1', 'construction': fallback_path,
                                        'construction_sha256': fallback_sha,
                                        'trigger': {'source': 'original Native history',
                                                    'metric': 'body-front position at first low-speed frame',
                                                    'failure_condition': 'body front crosses reviewed reference before yield response'},
                                        'changed_knobs': ['approach_hold_margin_m: 1.0 to 2.0']}],
                        'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                           'host_env_var': 'CARLA_HOST',
                                           'port_env_var': 'CARLA_PORT'}})
    write(ROOT / 'execution-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ROOT.name,
        'runtime_manifest_sha256': hashlib.sha256((REPO / 'runtime/SOURCE-MANIFEST.json').read_bytes()).hexdigest(),
        'diagnostic_only': True, 'cases': entries})
    (ROOT / 'config.json').write_text((ROOT / 'cases' /
        plan['cases'][0]['case_id'].removeprefix(ROOT.name + '__') / 'config.json').read_text())
    first = json.loads((ROOT / entries[0]['construction']).read_text())
    write(ROOT / 'construction.json', first)
    print('built exact source-gated yield constructions:', len(entries))


if __name__ == '__main__':
    main()

"""Materialize three exact diagnostic bicycle constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE_FILES = ('runner.py', 'native_adapter.py', 'native_site.py',
                'reviewed_site.py', 'native_measurement.py', 'analysis.py')
CAMERAS = ['overview', 'approach', 'reference_corner', 'driver_reference']
TEST = '''import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_site import verify

class BundleTest(unittest.TestCase):
    def test_exact_config(self):
        self.assertTrue(check_config(json.loads(Path('config.json').read_text())))
    def test_original_source_gate(self):
        with self.assertRaises(ValueError):
            verify(Path('missing-reviewed-site.json'))
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    expected = sorted(row['case_id'] for row in plan['cases'])
    if len(expected) != 3 or len(plan['comparisons']) != 2:
        raise ValueError('exact bicycle roster differs')
    entries = []
    for i, case in enumerate(plan['cases']):
        case_id = case['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case_id,
                  'supported_case_ids': expected, 'rate_hz': 20,
                  'duration_s': 45, 'diagnostic_only': True,
                  'engineering_speed_scale': 1.0,
                  'physical_completion': {
                      'criterion': 'travel_progress', 'motion_source': 'trace.jsonl',
                      'position_key': 'position_m', 'minimum_progress_m': 8.0,
                      'completion_goal_method': 'Observed progress across the 10 m source route; engineering milestone only, not a legal threshold'},
                  'cameras': CAMERAS, 'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id, 'motion': case['motion']}}
        files = [{'path': name, 'content': (HERE / name).read_text(encoding='utf-8')}
                 for name in SOURCE_FILES]
        files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                      {'path': 'tests/test_bundle.py', 'content': TEST}])
        description = {'channels': [
            {'name': name, 'unit': 'source observation',
             'method': '20 Hz original bicycle/sign/route readback',
             'time_window': '45-second original episode',
             'reference_frame': 'same Native frame and simulation time',
             'uncertainty': 'Physical roadway boundary and sign visibility need original review',
             'sampling_rate_hz': 20}
            for name in ('bicycle position and velocity', 'posted sign and roadway segment',
                         'four synchronized camera views')],
            'context_inputs': [{'name': 'reviewed designation sign route and bicycle',
                                'unit': 'source record',
                                'method': 'SHA-256 sealed original site packet'}],
            'limitations': ['Diagnostic fixture pixels and context are not original evidence.',
                            'City designation, sign governance, bicycle classification and legal outcome need review.']}
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'files': files, 'recording_description': description,
                        'mechanisms': ['reviewed City Traffic Engineer bicycle roadway designation',
                                       'source-bound erected governing sign',
                                       'connected trail-to-governed-roadway bicycle route',
                                       'four synchronized Native cameras'],
                        'measurement_plan': ['900 original 20 Hz bicycle segment readbacks',
                                             'source-joined sign and route readback',
                                             'four-camera decode'],
                        'static_checks': ['reviewed original site packet and eight source hashes',
                                          'exact requested bicycle route category'],
                        'termination_rules': {'frames': 900, 'native_sync_required': True}}
        rel = 'construction.json' if i == 0 else f'cases/{suffix}/construction.json'
        write(HERE / rel, construction)
        contract = {'format': 'worker-measurement-contract',
                    'requirements': [{'disposition_index': 0,
                                      'requirement': plan['law_text'],
                                      'source': plan['requirement_dispositions'][0]['source'],
                                      'output_key': 'bicycle_roadway_use',
                                      'method': 'sealed_original_bicycle_segment_projection',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['capture-packet.json', 'site-source.json']}],
                    'negative': {'remove': ['site-source.json'],
                                 'error_contains': 'Missing required source: site-source.json'}}
        contract_rel = 'measurement-contract.json' if i == 0 else f'cases/{suffix}/measurement-contract.json'
        write(HERE / contract_rel, contract)
        candidates = []
        risk = {'status': 'none',
                'reason': 'The nonentry route has no additional source-supported alternate geometry; original site and capture still need preflight.'}
        if suffix == 'posted_enter':
            fallback = json.loads(json.dumps(construction))
            fallback_config = {**config, 'engineering_speed_scale': 0.5}
            next(f for f in fallback['files'] if f['path'] == 'config.json')['content'] = json.dumps(fallback_config, indent=2) + '\n'
            fallback_rel = 'cases/posted_enter/fallback1-construction.json'
            write(HERE / fallback_rel, fallback)
            candidates.append({'id': 'fallback1', 'construction': fallback_rel,
                               'construction_sha256': sha(HERE / fallback_rel),
                               'trigger': {'source': 'original Native capture 900-frame bicycle position/segment readback',
                                           'metric': 'route-entry continuity and junction tracking',
                                           'failure_condition': 'primary route fails to enter governed roadway after trail or bicycle control deviates at junction'},
                               'changed_knobs': ['engineering_speed_scale: 1.0 to 0.5']})
            risk = {'status': 'physical',
                    'reason': 'The narrow trail-to-roadway junction may prevent stable entry; a slower source-preserving bicycle control is predeclared.'}
        entries.append({'case_id': case_id, 'kind': 'diagnostic',
                        'construction': rel, 'construction_sha256': sha(HERE / rel),
                        'measurement_contract': contract_rel,
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'fixture_recipe': f'work/{HERE.name}/cases/{suffix}/diagnostic-recipe.json',
                        'candidate_risk': risk,
                        'candidates': candidates})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'diagnostic_only': True, 'cases': entries}
    write(HERE / 'diagnostic-execution-manifest.json', manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(HERE / 'diagnostic-execution-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))

"""Materialize four exact diagnostic constructions without original-source claims."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_direction import CASES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE_FILES = ('runner.py', 'native_adapter.py', 'one_way_direction.py', 'reviewed_source.py', 'analysis.py')
TEST = '''import json
import unittest
from pathlib import Path
from runner import check_config
from reviewed_source import verify


class BundleTest(unittest.TestCase):
    def test_exact_config(self):
        config = json.loads(Path('config.json').read_text())
        self.assertTrue(check_config(config))

    def test_original_source_gate(self):
        config = json.loads(Path('config.json').read_text())
        with self.assertRaises(ValueError):
            verify(Path('missing-reviewed-site.json'), config['case']['variant'])
'''


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def build() -> dict:
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    expected = {ASSIGNMENT + '__' + case.name for case in CASES}
    if {row['case_id'] for row in plan['cases']} != expected:
        raise ValueError('exact case roster differs')
    entries = []
    for i, case in enumerate(CASES):
        case_id = ASSIGNMENT + '__' + case.name
        config = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'selected_case_id': case_id,
                  'supported_case_ids': sorted(expected), 'rate_hz': 20,
                  'duration_s': 45, 'diagnostic_only': True,
                  'reverse_motion': case.direction == 'opposed',
                  'requested_speed_mps': 5.0,
                  'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                  'required_atoms': [], 'source_packets': [],
                  'case': {'case_id': case_id, 'variant': case.name,
                           'lane': case.lane, 'direction': case.direction}}
        files = [{'path': name, 'content': (HERE / name).read_text(encoding='utf-8')}
                 for name in SOURCE_FILES]
        files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                      {'path': 'tests/test_bundle.py', 'content': TEST}])
        construction = {'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                        'actor': plan['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'files': files,
                        'recording_description': {
                            'channels': [
                                {'name': name, 'unit': 'source observation',
                                 'method': '20 Hz original Native source and camera readback',
                                 'time_window': '45-second original episode',
                                 'reference_frame': 'same original Native frame and simulation time',
                                 'uncertainty': 'Original motion, sign governance and physical pixels require review',
                                 'sampling_rate_hz': 20}
                                for name in ('original ego position and velocity',
                                             'same-direction lane and one-way sign governance',
                                             'four synchronized camera views')],
                            'context_inputs': [
                                {'name': 'reviewed highway, designation and sign authority',
                                 'unit': 'source record',
                                 'method': 'SHA-256 sealed original site and sign authority'}],
                            'limitations': [
                                'Diagnostic fixture pixels and context are not original evidence.',
                                'Actual sign governance and public highway status require independent review.']},
                        'mechanisms': ['reviewed public highway with at least two one-way lanes',
                                       'source-reviewed authorized governing sign',
                                       'ego route with actual designated or opposed velocity',
                                       'four synchronized cameras'],
                        'measurement_plan': ['900 original 20 Hz position and velocity rows',
                                             'original lane and sign source joins',
                                             'full four-camera decode'],
                        'static_checks': ['reviewed original site packet and 11 source hashes',
                                           'exact lane and direction route'],
                        'termination_rules': {'frames': 900, 'native_sync_required': True}}
        rel = 'construction.json' if i == 0 else f'cases/{case.name}/construction.json'
        write(HERE / rel, construction)
        contract = {'format': 'worker-measurement-contract',
                    'requirements': [{'disposition_index': 0,
                                      'requirement': plan['law_text'],
                                      'source': plan['requirement_dispositions'][0]['source'],
                                      'output_key': 'one_way_direction_observation',
                                      'method': 'original_position_velocity_projection',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['native-frames.jsonl', 'site-source.json']}],
                    'negative': {'remove': ['site-source.json'],
                                 'error_contains': 'Missing required source: site-source.json'}}
        contract_rel = 'measurement-contract.json' if i == 0 else f'cases/{case.name}/measurement-contract.json'
        write(HERE / contract_rel, contract)
        entries.append({'case_id': case_id, 'kind': 'diagnostic',
                        'construction': rel, 'construction_sha256': sha(HERE / rel),
                        'measurement_contract': contract_rel,
                        'measurement_procedure': {'entrypoint': 'analysis.py'},
                        'fixture_recipe': str((HERE / f'cases/{case.name}/diagnostic-recipe.json').relative_to(HERE.parent.parent)),
                        'candidate_risk': {'status': 'none',
                                           'reason': 'Reverse route and physical sign governance need original capture; no reviewed alternate site or trigger exists.'},
                        'candidates': []})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(REPO / 'runtime/SOURCE-MANIFEST.json'),
                'diagnostic_only': True, 'cases': entries}
    write(HERE / 'diagnostic-execution-manifest.json', manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(HERE / 'diagnostic-execution-manifest.json')}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))

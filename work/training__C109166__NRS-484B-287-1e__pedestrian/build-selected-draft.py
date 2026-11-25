"""Generate exact selected diagonal constructions; leaves delivery unproven."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
CAMERAS = [('overview', 1920, 1080), ('approach', 1280, 720),
           ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
TERMS = ('ru.subject', 'ru.pedestrian', 'dev.pedestrian_signal',
         'dev.regulatory_sign', 'dev.governs', 'st.intersection',
         'kin.position', 'kin.heading', 'kin.path_length', 'kin.time', 'rel.occupies')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


TEST = '''import json
from pathlib import Path
import tempfile
import unittest
from runner import check
from finalize import diagonal_entry_measurement
HERE = Path(__file__).resolve().parent.parent
class ExactDiagonalOffline(unittest.TestCase):
    def test_exact_runner(self):
        cfg = json.loads((HERE/'config.json').read_text())
        value = check(cfg)
        self.assertEqual(value['frames'], 600)
        self.assertEqual(value['camera_count'], 4)
        self.assertFalse(value['native_executed'])
    def test_missing_original_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Missing required source: video_frames.jsonl'):
                diagonal_entry_measurement(Path(tmp))
'''


def build():
    assignment = json.loads((ROOT/'inputs'/BASE/'assignment.json').read_text())
    if assignment['law']['text'] != json.loads((HERE/'case-plan.json').read_text())['source_law']['text']:
        raise ValueError('frozen law and plan differ')
    ids = [BASE + '__controlled_1', BASE + '__controlled_2']
    desc = {'channels': [{'name': name, 'unit': 'structured' if name.startswith(('dev.', 'rel.', 'st.', 'ru.')) else 'm_or_s',
             'sampling_rate_hz': 20, 'method': 'saved original Native pose, device and frame joins',
             'time_window': 'entire original 600-frame 30-second attempt',
             'reference_frame': 'original Native frame and time',
             'uncertainty': '50 ms sample brackets; physical authority and pixels pending independent review',
             'source': 'channels/' + name + '.jsonl'} for name in TERMS],
            'context_inputs': [{'name': 'diagonal_authority_source', 'unit': 'source',
                                'method': 'independent original survey pending'}],
            'limitations': ['Original surveyed authorization, actual device pixels and legal exception pending review']}
    inline = {name: (HERE/'native'/source).read_text() for name, source in (
        ('runner.py', 'capture_runner.py'), ('native_request.py', 'native_request.py'),
        ('original_source_audit.py', 'original_source_audit.py'), ('finalize.py', 'finalize.py'))}
    entries = []
    for suffix in ('controlled_1', 'controlled_2'):
        for candidate in ('primary', 'fallback1'):
            case_id = BASE + '__' + suffix
            config = {'case_id': case_id, 'selected_case_id': case_id,
                      'case': {'case_id': case_id, 'recording_description': desc},
                      'case_suffix': suffix, 'candidate_id': candidate,
                      'cell_id': 'C109166', 'law_id': 'NRS-484B-287-1e', 'actor': 'pedestrian',
                      'duration_s': 30, 'rate_hz': 20, 'supported_case_ids': ids,
                      'required_atoms': ['ru.pedestrian', 'kin.position', 'kin.heading', 'rel.occupies'],
                      'source_packets': [], 'opendrive_signal_id': 'candidate-unverified-203',
                      'entry_proxy_x_m': -5.5,
                      'driver_reference_height_m': 3.0 if candidate == 'primary' else 2.2,
                      'cameras': [{'name': name, 'width': width, 'height': height,
                                   'pose_strategy': 'fixed surveyed diagonal view',
                                   'fov_deg': 90}
                                  for name, width, height in CAMERAS],
                      'recording_description': desc}
            files = [{'path': name, 'content': content} for name, content in inline.items()]
            files += [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                      {'path': 'tests/test_offline.py', 'content': TEST}]
            construction = {'case_id': case_id, 'cell_id': 'C109166',
                'law_id': 'NRS-484B-287-1e', 'actor': 'pedestrian',
                'entrypoint': 'runner.py', 'files': files,
                'recording_description': desc,
                'measurement_plan': {'method': 'original first-entry pedestrian/device frame join',
                                     'status': 'source_shaped_cpu_draft'},
                'static_checks': ['600 original frames', 'four RGB source cameras',
                                  'independent diagonal authorization files'],
                'termination_rules': ['30-second capture', 'retain error and restoration report'],
                'mechanisms': ['same intersection and pedestrian route',
                               'CARLA walker control', 'source-gated physical signal state',
                               'independent original device and pixel review'],
                'status': 'selected_cpu_draft_no_public_receipt'}
            path = HERE/'cases'/suffix/candidate/'construction.json'
            write(path, construction)
            if suffix == 'controlled_1' and candidate == 'primary':
                write(HERE/'construction.json', construction)
                for name, content in inline.items():
                    (HERE/name).write_text(content)
                write(HERE/'config.json', config)
                (HERE/'tests').mkdir(exist_ok=True)
                (HERE/'tests/test_offline.py').write_text(TEST)
            if candidate == 'primary':
                contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
                    'requirements': [{'disposition_index': 0,
                        'requirement': 'NRS-484B-287-1e', 'source': 'NRS 484B.287(1)(e)',
                        'output_key': 'diagonal_first_entry_instruction',
                        'method': 'diagonal_entry_measurement', 'value_type': 'object',
                        'kind': 'measured',
                        'inputs': ['pedestrian-original.jsonl', 'device-original.jsonl',
                                   'authority-receipt.json']}],
                    'negative': {'remove': ['device-original.jsonl'],
                                 'error_contains': 'Missing required source: device-original.jsonl'}}
                contract_path = HERE/'cases'/suffix/'measurement-contract.json'
                write(contract_path, contract)
                entries.append({'case_id': case_id, 'kind': 'delivery',
                    'construction': str(path.relative_to(HERE)),
                    'construction_sha256': sha(path),
                    'measurement_contract': str(contract_path.relative_to(HERE)),
                    'measurement_procedure': {'entrypoint': 'finalize.py',
                                              'output_schema': 'worker-analysis-report-v1'},
                    'fixture_recipe': f'work/{BASE}/diagnostic-{suffix}-recipe.json',
                    'candidate_risk': {'status': 'physical',
                        'reason': 'Original display glyph may be vertically foreshortened in the detail view'},
                    'candidates': []})
            else:
                entries[-1]['candidates'].append({'id': 'fallback1',
                    'construction': str(path.relative_to(HERE)),
                    'construction_sha256': sha(path),
                    'trigger': {'source': 'original driver_reference camera pixels',
                                'metric': 'diagonal glyph visible height in pixels',
                                'failure_condition': 'glyph visible height below 12 pixels in primary'},
                    'changed_knobs': ['driver_reference_height_m: 3.0 to 2.2']})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE,
                'runtime_manifest_sha256': json.loads((ROOT/'batch.json').read_text())['runtime']['source_manifest_sha256'],
                'status': 'selected_cpu_draft_no_public_receipt', 'delivery_ready': False,
                'original_native_observed': False, 'cases': entries}
    write(HERE/'execution-manifest.json', manifest)
    proposal = {'cell_id': 'C109166', 'actor': 'pedestrian', 'status': 'draft',
                'sweep_specs': [], 'sweeps_expanded': [], 'cases': []}
    for suffix, instruction in (('baseline', None), ('controlled_1', 'diagonal_walk'),
                                ('controlled_2', 'diagonal_dont_walk')):
        proposal['cases'].append({'case_id': BASE+'__'+suffix,
            'target_law_id': None if suffix == 'baseline' else 'NRS-484B-287-1e',
            'target_type': 'baseline' if suffix == 'baseline' else 'judgment_sweep',
            'rationale': 'Unselected context' if suffix == 'baseline' else
                         'Source-bound first-entry instruction contrast on one diagonal route',
            'variable_assignments': {
                'requested_first_entry_instruction': {'kind': 'world_setup', 'value': instruction},
                'diagonal_authorization': {'kind': 'sourced_context',
                                            'value': 'original survey pending'}},
            'unresolved_judgment_calls': ['authorized to cross diagonally',
                'official traffic-control devices pertaining to such crossing movements',
                'Except as provided in NRS 484B.290'],
            'recording_description': desc})
    write(HERE/'proposals/cases.json', proposal)
    print(json.dumps({'cases': len(entries), 'constructions': 4,
                      'manifest_sha256': sha(HERE/'execution-manifest.json')}))


if __name__ == '__main__':
    build()

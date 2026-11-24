"""Inline the two source-bound, unselected timing constructions for runtime.py offline."""
import hashlib
import json
from pathlib import Path

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[1]

ENTRY = '''"""C179480 CPU timing diagnostic; Native recording remains unimplemented."""
import argparse
import hashlib
import json
from pathlib import Path

def check():
    root = Path.cwd()
    source = json.loads((root / 'assignment-source.json').read_text())
    plan = json.loads((root / 'case-plan.json').read_text())
    config = json.loads((root / 'config.json').read_text())
    assert source['assignment_id'] == plan['assignment_id'] == config['assignment_id']
    assert source['law']['text'] == plan['source_law']['text']
    assert source['law_sha256'] == plan['source_law']['sha256']
    assert config['brake_lamp_command_frame'] in (100, 121)
    assert config['rate_hz'] == 20 and config['frames'] == 600
    assert config['source_camera_names'] == ['overview', 'approach', 'reference_corner', 'driver_reference']
    return {'source_bound': True, 'native_executed': False, 'delivery_ready': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise RuntimeError('Native execution has not been implemented for this draft')
    print(json.dumps(check()))
'''

TEST = '''import json
import unittest
from pathlib import Path
from capture import check

class DraftTest(unittest.TestCase):
    def test_source_bound(self):
        result = check()
        self.assertTrue(result['source_bound'])
        self.assertFalse(result['delivery_ready'])
        self.assertFalse(result['native_executed'])

    def test_exact_control(self):
        config = json.loads(Path('config.json').read_text())
        expected = 100 if config['case_id'].endswith('witness_1') else 121
        self.assertEqual(config['brake_lamp_command_frame'], expected)
        self.assertEqual(config['action_frame'], 120)
        self.assertEqual(config['rear_gap_m'], 12.0)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / CASE.name / 'assignment.json').read_text())
    plan = json.loads((CASE / 'case-plan.json').read_text())
    law = {'assignment_id': CASE.name, 'law': assignment['law'],
           'law_sha256': assignment['local_snapshot']['law_sha256']}
    entries = []
    for suffix, signal_frame in (('witness_1', 100), ('witness_2', 121)):
        case_id = CASE.name + '__' + suffix
        config = {'assignment_id': CASE.name, 'case_id': case_id,
                  'cell_id': 'C179480', 'law_id': 'NRS-484B-413-3',
                  'actor': 'motor_vehicle_driver', 'frozen_cell': plan['frozen_cell'],
                  'rate_hz': 20, 'frames': 600, 'duration_s': 30,
                  'action_frame': 120, 'brake_lamp_command_frame': signal_frame,
                  'rear_gap_m': 12.0, 'diagnostic_deceleration_mps2': 3.0,
                  'source_camera_names': ['overview', 'approach',
                                          'reference_corner', 'driver_reference'],
                  'source_rows_required': ['actor-sources.jsonl', 'camera-frames.jsonl'],
                  'native_execution_implemented': False}
        files = [{'path': 'capture.py', 'content': ENTRY},
                 {'path': 'tests/test_draft.py', 'content': TEST},
                 {'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                 {'path': 'assignment-source.json', 'content': json.dumps(law, indent=2) + '\n'},
                 {'path': 'case-plan.json', 'content': json.dumps(plan, indent=2) + '\n'},
                 {'path': 'measure_timing.py', 'content': (CASE / 'measure_timing.py').read_text()}]
        proposal = {'case_id': case_id, 'cell_id': 'C179480',
                    'law_id': 'NRS-484B-413-3', 'actor': 'motor_vehicle_driver',
                    'status': 'unselected_cpu_diagnostic', 'entrypoint': 'capture.py',
                    'files': files, 'recording_description':
                    'Original Native stop, immediately rear vehicle and observed lamp state remain unrecorded.'}
        path = CASE / 'offline' / 'drafts' / suffix / 'construction.json'
        write(path, proposal)
        entries.append({'case_id': case_id,
                        'construction': str(path.relative_to(CASE)),
                        'construction_sha256': sha(path),
                        'candidates': [], 'candidate_risk': {
                            'status': 'physical',
                            'reason': 'Native stop, rear relation and observed signal have not been measured.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    path = CASE / 'draft-execution-manifest.json'
    write(path, manifest)
    return path


if __name__ == '__main__':
    print(build())

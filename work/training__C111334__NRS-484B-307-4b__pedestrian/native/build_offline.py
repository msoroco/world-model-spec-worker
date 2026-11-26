"""Build exact, source-bound C111334 Native bundles for CPU offline checks."""
import hashlib
import json
from pathlib import Path

from construction import ASSIGNMENT, CASES, HERE, proposal

FOLDER = HERE.parent
FILES = ('runner.py', 'construction.py', 'control.py', 'signals.py',
         'selected_finalize.py', 'road.xodr')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def test_source(suffix):
    return '''import json
import unittest
from pathlib import Path
from runner import check
from construction import check_comparisons
from control import command

ROOT = Path(__file__).resolve().parents[1]


class ExactCase(unittest.TestCase):
    def test_construction_and_controller(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual(config['case_suffix'], %r)
        result = check(config)
        self.assertEqual(result['frames'], 600)
        self.assertEqual(len(result['camera_views']), 4)
        self.assertFalse(result['native_executed'])
        self.assertEqual(len(check_comparisons()['case_ids']), 3)
        self.assertEqual(command(config['case_suffix'], 599)['frame'], 599)
        with self.assertRaisesRegex(ValueError, 'outside 600-frame'):
            command(config['case_suffix'], 600)


if __name__ == '__main__':
    unittest.main()
''' % suffix


def build():
    entries = []
    for suffix in CASES:
        plan = proposal(suffix)
        config = json.loads((HERE / 'config.json').read_text())
        config.update(case_id=plan['case_id'], selected_case_id=plan['case_id'],
                      case_suffix=suffix,
                      requested_permission_start_frame=plan['requested_permission_start_frame'],
                      requested_walker_move_start_frame=plan['requested_walker_move_start_frame'])
        files = [{'path': name, 'content': (HERE / name).read_text(),
                  'source': str((HERE / name).relative_to(FOLDER.parents[1]))}
                 for name in FILES]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        files.append({'path': 'tests/test_offline.py', 'content': test_source(suffix)})
        construction = {
            'case_id': plan['case_id'], 'cell_id': 'C111334',
            'law_id': 'NRS-484B-307-4b', 'actor': 'pedestrian',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': config['recording_description'],
            'measurement_plan': {'method': 'source_join_measurement',
                                 'entrypoint': 'finalize_original.py'},
            'status': 'exact_native_request_physical_unverified',
        }
        path = FOLDER / 'native-selected' / suffix / 'construction.json'
        save(path, construction)
        disposition_index = 1 if suffix == 'permission_before_entry' else 0
        save(path.parent / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'case_id': plan['case_id'],
            'requirements': [{
                'disposition_index': disposition_index,
                'requirement': 'NRS-484B-307-4b',
                'source': 'NRS 484B.307(4)(b)',
                'output_key': 'pedestrian_entry_measurement',
                'method': 'source_join_measurement', 'kind': 'measured',
                'value_type': 'object', 'inputs': list(('c111334-native-samples.jsonl',
                                                        'video_frames.jsonl', 'device-review.json')),
            }],
            'negative': {'remove': ['device-review.json'],
                         'error_contains': 'Missing required source: device-review.json'},
            'frame_count': 600, 'sampling_rate_hz': 20, 'duration_s': 30,
            'physical_acceptance_claimed': False,
            'source_required': plan['required_original_sources'],
            'source_finalizer': 'native/selected_finalize.py',
            'original_native_observed': False, 'legal_verdict': None,
        })
        entries.append({'case_id': plan['case_id'], 'kind': 'delivery',
                        'construction': str(path.relative_to(FOLDER / 'native-selected')),
                        'construction_sha256': digest(path),
                        'measurement_contract': str((path.parent / 'measurement-contract.json').relative_to(FOLDER / 'native-selected')),
                        'measurement_procedure': {'entrypoint': 'selected_finalize.py'}})
    save(FOLDER / 'native-selected' / 'offline-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
        'runtime_manifest_sha256': digest(FOLDER.parents[1] / 'runtime' / 'SOURCE-MANIFEST.json'),
        'delivery_ready': False, 'status': 'offline_construction_only',
        'cases': entries,
    })
    return entries


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))

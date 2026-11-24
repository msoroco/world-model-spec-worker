"""CPU check of the exact-case delivery acceptance evidence and source bindings."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(case_id, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((row for row in manifest['cases'] if row['case_id'] == case_id), None)
    if entry is None:
        raise ValueError('Unknown exact case')
    suffix = case_id.rsplit('__', 1)[-1]
    compat_path = HERE / 'selected-proof' / suffix / 'primary/compatibility.json'
    compat = json.loads(compat_path.read_text())
    if compat['case_id'] != case_id or not compat['passed']:
        raise ValueError('Selected compatibility receipt failed')
    if compat['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Selected construction changed')
    required = {'acquisition_unchanged', 'actual_analysis', 'derived_outputs_rebuilt',
                'final_decode', 'four_camera_sources', 'lean_decoder',
                'mandatory_observations', 'native_validation', 'render',
                'selected_measurements', 'negative_case_source'}
    if not required <= set(compat['checks']):
        raise ValueError('Selected compatibility checks incomplete')
    negative_log = HERE / entry['compatibility']['negative_log']
    if compat['negative_error_contains'] not in negative_log.read_text():
        raise ValueError('Missing-source negative did not reject')
    physical_path = HERE / entry['physical_preparation']['receipt']
    physical = json.loads(physical_path.read_text())
    if sha(physical_path) != entry['physical_preparation']['sha256']:
        raise ValueError('Physical preparation changed')
    statuses = {item['kind']: json.loads((HERE / item['result']).read_text())
                ['physical_checks']['maneuver']['status'] for item in physical['fixtures']}
    if statuses != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}:
        raise ValueError('Physical fixture outcomes incomplete')
    if negative:
        raise ValueError('Missing independent original Native and physical acceptance source')
    return {'case_id': case_id, 'checks': list(CHECKS), 'sets': ['full-train'],
            'cpu_diagnostic_only': True, 'native_capture_observed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.negative)))

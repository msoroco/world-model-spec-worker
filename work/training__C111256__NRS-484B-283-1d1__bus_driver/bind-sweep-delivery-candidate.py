"""Bind four staged sweep primaries to audited diagnostic/rejection commands."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    base_path = HERE / 'sweep-proof-bound-promotion-candidate.json'
    matrix_path = HERE / 'update033-sweep-delivery-audit-matrix.json'
    manifest = read(base_path)
    matrix = read(matrix_path)
    if (len(manifest['cases']) != 4 or len(matrix['rows']) != 4 or
            matrix['manifest_sha256'] != sha(base_path) or
            matrix['auditor_sha256'] != sha(HERE / 'sweep_delivery_audit.py')):
        raise ValueError('Incomplete or stale staged sweep delivery audit')
    rows = {row['case_id']: row for row in matrix['rows']}
    selected = read(HERE / 'execution-manifest.json')
    reference = next(entry for entry in selected['cases']
                     if entry['case_id'].endswith('__reference'))
    for entry in manifest['cases']:
        case_id = entry['case_id']
        row = rows[case_id]
        if (row['construction_sha256'] != entry['construction_sha256'] or
                row['negative_exit_code'] == 0 or
                row['original_recordings_accepted'] != 0):
            raise ValueError('Sweep delivery proof source or rejection differs')
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'sweep_delivery_audit.py',
            'script_sha256': sha(HERE / 'sweep_delivery_audit.py'),
            'command': row['diagnostic_command'],
            'test_exit_code': 0,
            'test_log': row['diagnostic_log'],
            'test_log_sha256': row['diagnostic_log_sha256'],
            'negative_command': row['negative_command'],
            'negative_exit_code': row['negative_exit_code'],
            'negative_expected_error': row['negative_expected_error'],
            'negative_log': row['negative_log'],
            'negative_log_sha256': row['negative_log_sha256']}
        post = dict(reference['post_capture'])
        post['command'] = post['command'].replace(reference['case_id'], case_id)
        post['test_log'] = row['process_log']
        post['test_log_sha256'] = row['process_log_sha256']
        entry['post_capture'] = post
        validate_case(HERE, entry, {'full-train'})
    manifest['source_delivery_matrix_sha256'] = sha(matrix_path)
    manifest['source_proof_bound_candidate_sha256'] = sha(base_path)
    manifest['status'] = 'delivery_bound_promotion_candidate_not_selected'
    path = HERE / 'sweep-delivery-bound-candidate.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']),
                      'pinned_delivery_contract_validator': 'passed',
                      'selected': False, 'original_recordings_accepted': 0,
                      'sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()

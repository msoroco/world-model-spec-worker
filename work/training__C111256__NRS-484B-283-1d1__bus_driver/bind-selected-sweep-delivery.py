"""Bind canonical sweep delivery audit commands after selected CPU proof."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    matrix_path = HERE / 'update037-selected-sweep-delivery-matrix.json'
    manifest = read(manifest_path)
    matrix = read(matrix_path)
    rows = {row['case_id']: row for row in matrix['rows']}
    selected = {entry['case_id'] for entry in manifest['cases']
                if '__right_of_way_physical_context-' in entry['case_id']}
    if (len(manifest['cases']) != 6 or len(rows) != 4 or set(rows) != selected or
            matrix['manifest_sha256'] != sha(manifest_path) or
            matrix['auditor_sha256'] != sha(HERE / 'sweep_delivery_audit.py')):
        raise ValueError('Selected sweep delivery matrix differs from canonical manifest')
    for entry in manifest['cases']:
        if entry['case_id'] not in selected:
            continue
        row = rows[entry['case_id']]
        if row['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Selected sweep construction changed')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'sweep_delivery_audit.py',
            'script_sha256': sha(HERE / 'sweep_delivery_audit.py'),
            'command': row['diagnostic_command'], 'test_exit_code': 0,
            'test_log': row['diagnostic_log'],
            'test_log_sha256': row['diagnostic_log_sha256'],
            'negative_command': row['negative_command'],
            'negative_exit_code': row['negative_exit_code'],
            'negative_expected_error': row['negative_expected_error'],
            'negative_log': row['negative_log'],
            'negative_log_sha256': row['negative_log_sha256']}
        validate_case(HERE, entry, {'full-train'})
    manifest['status'] = 'partial_six_selected_delivery_bound_saved_reproof_pending'
    manifest['selected_sweep_delivery_matrix_sha256'] = sha(matrix_path)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'bound_selected_sweep_cases': 4,
                      'manifest_sha256': sha(manifest_path),
                      'saved_processing_reproof_pending': True,
                      'original_recordings_accepted': 0}, sort_keys=True))


if __name__ == '__main__':
    main()

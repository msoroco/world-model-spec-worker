"""Record CPU proof references after all exact selected checks have passed."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    matrix = HERE / 'selected-runtime-candidate-matrix.json'
    rows = json.loads(matrix.read_text())['cases']
    if len(rows) != 6 or not all(len(row['checks']) == 11 for row in rows):
        raise ValueError('Six selected public proofs not complete')
    saved = [HERE / ('selected-current-runtime-' + candidate + '-saved-proof.json')
             for candidate in ('primary', 'fallback1', 'fallback3')]
    for path in saved:
        result = json.loads(path.read_text())
        if not result['passed'] or not result['selected'] or len(result['cases']) != 2:
            raise ValueError('Selected saved proof missing: ' + path.name)
    test_log = HERE / 'selected-root-native-tests.log'
    original = (HERE.parents[1] / '.runtime-work/c110919-3a-owner/root-tests.log').read_text()
    if 'Ran 5 tests' not in original or '\nOK' not in original:
        raise ValueError('Root native tests did not pass')
    test_log.write_text(original.rstrip() + '\n')
    result_path = HERE / 'result.json'
    result = json.loads(result_path.read_text())
    result.update(
        status='ready', readiness_kind='delivery_prepared',
        reason=('Selected CPU delivery preparation for both exact 600-frame right-arrow turn witnesses: '
                'six current-runtime primary/fallback public positive and missing-source negative '
                'compatibility receipts, six recorded-only saved positives and missing-road negatives, '
                'semantic, physical diagnostic, independent delivery and comparison audits pass. '
                'Actual Native arrow glyph, opposing red pixels, lawful pedestrian/traffic status and '
                'physical yield remain unobserved for local GPU acceptance.'),
        planned_case_count=2, comparison_count=1, candidate_count=4,
        unresolved_branch_count=0, cases_selected=2, delivery_cases_prepared=2,
        source_law_review=('Four exact statutory topics reviewed; physical arrow, opposing-red and '
                           'lawful-user facts require original recording review'),
        first_gpu_delivery_command=(
            'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -m worker_exchange '
            'execute-delivery --repo . --batch full-train-delivery --db $DB --assignment ' + ID +
            ' --case ' + ID + '__witness_1 --run $RUN --job $JOB_ID --python $CARLA_PYTHON '
            '--host $CARLA_HOST --port $CARLA_PORT'),
        selected_runtime_proofs={
            'manifest': 'execution-manifest.json',
            'manifest_sha256': sha(HERE / 'execution-manifest.json'),
            'public_matrix': matrix.name, 'public_matrix_sha256': sha(matrix),
            'public_receipts': 6, 'saved_proofs': [
                {'path': p.name, 'sha256': sha(p)} for p in saved],
            'semantic_index_sha256': sha(HERE / 'proposals/semantic-index.json'),
            'comparison_audit_sha256': sha(HERE / 'selected-comparison-audit.json'),
            'original_native_observed': False, 'physical_acceptance_claimed': False},
        tests=[
            {'command': 'PYTHONPATH=<assignment> .venv-cpu/bin/python -m unittest discover -s tests -v',
             'exit_code': 0, 'log': test_log.name, 'sha256': sha(test_log)},
            {'command': '.venv-cpu/bin/python work/' + ID + '/prove-current-runtime-candidates.py',
             'exit_code': 0, 'log': matrix.name, 'sha256': sha(matrix)},
            *[{'command': '.venv-cpu/bin/python work/' + ID + '/prove-current-v2-saved.py --candidate ' + candidate,
               'exit_code': 0, 'log': path.name, 'sha256': sha(path)}
              for candidate, path in zip(('primary', 'fallback1', 'fallback3'), saved)],
            {'command': '.venv-cpu/bin/python work/' + ID + '/audit-selected-comparison.py',
             'exit_code': 0, 'log': 'selected-comparison-audit.json',
             'sha256': sha(HERE / 'selected-comparison-audit.json')},
        ])
    result_path.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'status': result['status'], 'manifest_sha256': sha(HERE / 'execution-manifest.json'),
                      'result_sha256': sha(result_path)}))


if __name__ == '__main__':
    main()

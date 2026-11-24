"""Bind six final selected-manifest public receipts without changing constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    matrix = json.loads((HERE / 'selected-runtime-candidate-matrix.json').read_text())
    rows = {(row['case_id'], row['candidate']): row for row in matrix['cases']}
    if len(rows) != 6 or not matrix['passed']:
        raise ValueError('Selected public matrix is incomplete')
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    if matrix['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']:
        raise ValueError('Runtime changed')
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        for candidate, spec in [('primary', entry)] + [(c['id'], c) for c in entry['candidates']]:
            row = rows[entry['case_id'], candidate]
            if row['construction_sha256'] != spec['construction_sha256']:
                raise ValueError('Construction changed: ' + witness + '/' + candidate)
            prefix = Path('selected-runtime-proofs') / witness / candidate
            receipt = HERE / prefix / 'compatibility.json'
            proof = json.loads(receipt.read_text())
            if (not proof['passed'] or proof['case_id'] != entry['case_id'] or
                    proof['candidate_id'] != candidate or
                    proof['construction_sha256'] != spec['construction_sha256'] or
                    proof['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256']):
                raise ValueError('Selected public receipt mismatch: ' + witness + '/' + candidate)
            for field, filename in [('receipt_sha256', 'compatibility.json'),
                                    ('offline_log_sha256', 'offline.log'),
                                    ('analysis_log_sha256', 'analysis.log'),
                                    ('negative_log_sha256', 'negative-analysis.log')]:
                if sha(HERE / prefix / filename) != row[field]:
                    raise ValueError('Selected public file changed: ' + witness + '/' + candidate)
            spec['compatibility'] = {
                'receipt': (prefix / 'compatibility.json').as_posix(),
                'sha256': row['receipt_sha256'],
                'log': (prefix / 'analysis.log').as_posix(),
                'negative_log': (prefix / 'negative-analysis.log').as_posix()}
            spec['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                           '/execution-manifest.json --case ' + entry['case_id'] +
                           ' --candidate ' + candidate + ' --output .runtime-work/c110919-3a-owner/selected-matrix/' +
                           witness + '-' + candidate + '/offline',
                'exit_code': 0,
                'construction_sha256': spec['construction_sha256'],
                'log': (prefix / 'offline.log').as_posix(),
                'log_sha256': row['offline_log_sha256']}
            if candidate == 'primary':
                entry['negative'] = {'log': (prefix / 'negative-analysis.log').as_posix()}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'manifest_sha256': sha(path), 'receipts': len(rows)}))


if __name__ == '__main__':
    main()

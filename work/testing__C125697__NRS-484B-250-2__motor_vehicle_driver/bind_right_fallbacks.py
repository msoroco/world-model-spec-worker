"""Bind current exact offline and compatibility receipts for ego-right retries."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name+'__off_ego_right_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(row for row in manifest['cases'] if row['case_id'] == CASE)
    for candidate in entry['candidates']:
        ident = candidate['id']
        construction_sha = sha(HERE/candidate['construction'])
        if construction_sha != candidate['construction_sha256']:
            raise ValueError(f'{ident} right construction changed')
        offline_log = HERE/f'right-{ident}-offline-v1.log'
        if '"offline_passed": true' not in offline_log.read_text():
            raise ValueError(f'{ident} right offline proof failed')
        candidate['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --candidate {ident} --output .runtime-work/c125697-right-{ident}-offline-v1',
            'exit_code': 0, 'construction_sha256': construction_sha,
            'log': offline_log.name, 'log_sha256': sha(offline_log),
        }
        attempt = REPO/f'.runtime-work/c125697-right-{ident}-compatibility-v1'
        copies = {
            'receipt': ('compatibility.json', f'right-{ident}-compatibility-receipt.json'),
            'log': ('compatibility-analysis.log', f'right-{ident}-compatibility-analysis.log'),
            'negative_log': ('negative-analysis.log', f'right-{ident}-negative-analysis.log'),
        }
        for source, destination in copies.values():
            shutil.copyfile(attempt/source, HERE/destination)
        receipt_path = HERE/copies['receipt'][1]
        receipt = json.loads(receipt_path.read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != CASE
                or receipt.get('candidate_id') != ident
                or receipt.get('construction_sha256') != construction_sha
                or receipt.get('log_sha256') != sha(HERE/copies['log'][1])
                or receipt.get('negative_log_sha256') != sha(HERE/copies['negative_log'][1])):
            raise ValueError(f'{ident} right compatibility proof differs')
        candidate['compatibility'] = {
            'receipt': receipt_path.name, 'sha256': sha(receipt_path),
            'log': copies['log'][1], 'negative_log': copies['negative_log'][1],
        }
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': CASE, 'bound': [c['id'] for c in entry['candidates']]}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))

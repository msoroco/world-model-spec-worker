"""Bind exact CPU fallback receipts for the first, still-partial case."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = HERE.name + '__off_ego_left_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = HERE/'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    for candidate in entry['candidates']:
        ident = candidate['id']
        construction_hash = sha(HERE/candidate['construction'])
        if construction_hash != candidate['construction_sha256']:
            raise ValueError(f'{ident} construction changed')
        log = HERE/f'{ident}-offline-v1.log'
        if '"offline_passed": true' not in log.read_text():
            raise ValueError(f'{ident} exact offline failed')
        candidate['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {CASE} --candidate {ident} --output .runtime-work/c125697-{ident}-offline-v1',
            'exit_code': 0, 'construction_sha256': construction_hash,
            'log': log.name, 'log_sha256': sha(log),
        }
        attempt = REPO/f'.runtime-work/c125697-{ident}-compatibility-v1'
        targets = {
            'receipt': (attempt/'compatibility.json', HERE/f'{ident}-compatibility-receipt.json'),
            'log': (attempt/'compatibility-analysis.log', HERE/f'{ident}-compatibility-analysis.log'),
            'negative_log': (attempt/'negative-analysis.log', HERE/f'{ident}-negative-analysis.log'),
        }
        for source, destination in targets.values():
            shutil.copyfile(source, destination)
        receipt = json.loads(targets['receipt'][1].read_text())
        if (receipt.get('passed') is not True or receipt.get('candidate_id') != ident
                or receipt.get('case_id') != CASE
                or receipt.get('construction_sha256') != construction_hash
                or receipt.get('log_sha256') != sha(targets['log'][1])
                or receipt.get('negative_log_sha256') != sha(targets['negative_log'][1])):
            raise ValueError(f'{ident} compatibility receipt differs')
        candidate['compatibility'] = {
            'receipt': targets['receipt'][1].name,
            'sha256': sha(targets['receipt'][1]),
            'log': targets['log'][1].name,
            'negative_log': targets['negative_log'][1].name,
        }
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'case_id': CASE, 'bound': [item['id'] for item in entry['candidates']]}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))

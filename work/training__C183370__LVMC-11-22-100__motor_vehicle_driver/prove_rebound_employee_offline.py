"""Reprove exact employee draft constructions after the governing-control change."""
import hashlib
import json
import subprocess
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-employee-capture-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    manifest = json.loads(MANIFEST.read_text())
    rows = []
    for case in manifest['cases']:
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = case if candidate == 'primary' else next(
                row for row in case['candidates'] if row['id'] == candidate)
            short = case['case_id'].removeprefix(PACKAGE.name + '__')
            label = short + '-' + candidate
            output = REPO / '.runtime-work' / ('c183370-update124-offline-' + label)
            log = PACKAGE / ('update124-offline-' + label + '.log')
            command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST), '--case', case['case_id'],
                       '--candidate', candidate, '--output', str(output)]
            with log.open('w') as stream:
                run = subprocess.run(command, cwd=REPO, stdout=stream,
                                     stderr=subprocess.STDOUT, check=False)
            if run.returncode:
                raise ValueError('Offline proof failed: ' + label + ': ' + log.read_text()[-1000:])
            receipt_path = output / 'candidate-selection.json'
            receipt = json.loads(receipt_path.read_text())
            if (receipt.get('case_id') != case['case_id'] or
                    receipt.get('candidate_id') != candidate or
                    receipt.get('manifest_sha256') != sha(MANIFEST) or
                    receipt.get('construction_sha256') != selected['construction_sha256']):
                raise ValueError('Offline receipt differs from rebound construction: ' + label)
            rows.append({'case_id': case['case_id'], 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'offline_receipt_sha256': sha(receipt_path),
                         'log': log.name, 'log_sha256': sha(log)})
            print(label, 'passed', flush=True)
    result = PACKAGE / 'update124-employee-rebound-offline-matrix.json'
    result.write_text(json.dumps({'format': 'c183370-employee-rebound-offline-v1',
                                  'manifest_sha256': sha(MANIFEST), 'rows': rows},
                                 indent=2, sort_keys=True) + '\n')
    return result


if __name__ == '__main__':
    print(prove())

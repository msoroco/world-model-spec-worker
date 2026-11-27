"""Bind exact B(3) offline and compatibility receipts to the selected case."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIX = 'mobility_device'
CASE_ID = HERE.name + '__' + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE_ID)
    for candidate_id, work_name, proof_name in (
            ('primary', 'primary', 'c143691-mobility-compat-primary-r3'),
            ('fallback1', 'fallback1', 'c143691-mobility-compat-fallback-r3')):
        binding = entry if candidate_id == 'primary' else entry['candidates'][0]
        expected = binding['construction_sha256']
        proof = ROOT / '.runtime-work' / proof_name
        receipt = json.loads((proof / 'compatibility.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != CASE_ID
                or receipt.get('candidate_id') != candidate_id
                or receipt.get('construction_sha256') != expected):
            raise ValueError('B(3) compatibility binding changed: ' + candidate_id)
        target = HERE / 'compatibility' / (SUFFIX + '-' + work_name + '.json')
        shutil.copyfile(proof / 'compatibility.json', target)
        analysis = HERE / 'compatibility' / (SUFFIX + '-' + work_name + '-analysis.log')
        negative = HERE / 'compatibility' / (SUFFIX + '-' + work_name + '-negative.log')
        shutil.copyfile(proof / 'compatibility-analysis.log', analysis)
        shutil.copyfile(proof / 'negative-analysis.log', negative)
        if sha(analysis) != receipt['log_sha256'] or sha(negative) != receipt['negative_log_sha256']:
            raise ValueError('B(3) compatibility logs changed')
        offline = HERE / 'offline' / (SUFFIX + '-' + work_name + '.log')
        offline_result = json.loads(offline.read_text())
        if (offline_result.get('offline_passed') is not True
                or offline_result.get('case_id') != CASE_ID
                or offline_result.get('candidate_id') != candidate_id):
            raise ValueError('B(3) offline proof changed')
        binding['offline'] = {
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/'
                       + HERE.name + '/execution-manifest.json --case ' + CASE_ID
                       + (' --candidate fallback1' if candidate_id == 'fallback1' else '')
                       + ' --output .runtime-work/c143691-mobility-selected-'
                       + ('fallback' if candidate_id == 'fallback1' else 'primary'),
            'exit_code': 0, 'construction_sha256': expected,
            'log': str(offline.relative_to(HERE)), 'log_sha256': sha(offline),
        }
        binding['compatibility'] = {
            'receipt': str(target.relative_to(HERE)), 'sha256': sha(target),
            'log': str(analysis.relative_to(HERE)),
            'negative_log': str(negative.relative_to(HERE)),
        }
        if candidate_id == 'primary':
            binding['negative'] = {'log': str(negative.relative_to(HERE))}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'case_id': CASE_ID, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

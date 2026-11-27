"""Retain exact four current-runtime offline receipts in the assignment draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]
manifest_path = ASSIGNMENT / 'draft-execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    for candidate in ('primary', 'fallback1'):
        source = ROOT / '.runtime-work' / f'c31675-offline-{suffix}-{candidate}-final3' / 'offline.log'
        if not source.is_file():
            raise ValueError('Missing exact current-runtime offline log: ' + str(source))
        content = source.read_text().rstrip() + '\n'
        if 'Ran 6 tests' not in content or not content.endswith('OK\n'):
            raise ValueError('Exact offline tests did not pass: ' + str(source))
        target = ASSIGNMENT / 'proofs' / suffix / (candidate + '-offline.log')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        proof = {'command': '.venv-cpu/bin/python runtime.py offline --manifest '
            + str(manifest_path.relative_to(ROOT)) + ' --case ' + entry['case_id']
            + ' --candidate ' + candidate + ' --output .runtime-work/c31675-offline-'
            + suffix + '-' + candidate + '-final3',
            'exit_code': 0, 'log': str(target.relative_to(ASSIGNMENT)),
            'log_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
            'construction_sha256': entry['construction_sha256'] if candidate == 'primary'
                                   else entry['candidates'][0]['construction_sha256'],
            'runtime': 'current'}
        if candidate == 'primary':
            entry['offline'] = proof
        else:
            entry['candidates'][0]['offline'] = proof
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'offline_proofs_bound': 4, 'case_ids': [c['case_id'] for c in manifest['cases']]}))

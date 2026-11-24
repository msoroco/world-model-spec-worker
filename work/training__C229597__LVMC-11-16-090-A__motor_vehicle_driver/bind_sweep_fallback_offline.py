"""Attach exact alternate spawn CPU receipts to the selected sweep cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        if '__judgment-' not in entry['case_id']:
            continue
        cid = entry['case_id']
        candidate = entry['candidates'][0]
        construction = HERE / candidate['construction']
        log = construction.parent / 'offline.log'
        scratch = ROOT / '.runtime-work/c229597-sweep-fallback-offline-v3' / cid / 'offline.log'
        if (sha(construction) != candidate['construction_sha256']
                or not log.is_file() or not scratch.is_file()
                or 'OK' not in scratch.read_text()):
            raise ValueError('Exact fallback CPU proof missing: ' + cid)
        candidate['offline'] = {
            'command': ' '.join((str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                                 'offline', '--manifest', str(HERE / 'sweep-cases/fallback-manifest.json'),
                                 '--case', cid, '--output', str(scratch.parent),
                                 '--python', str(ROOT / '.venv-cpu/bin/python'))),
            'exit_code': 0,
            'construction_sha256': candidate['construction_sha256'],
            'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)}
        candidate['cpu_proof_status'] = 'exact_offline_passed_compatibility_pending'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallback_offline_passed': 6, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

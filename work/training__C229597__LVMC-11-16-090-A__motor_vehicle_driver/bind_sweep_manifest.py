"""Bind exact sweep cases to the delivery manifest as proof-pending entries."""
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
    manifest['cases'] = [case for case in manifest['cases']
                         if '__judgment-' not in case['case_id']]
    index = json.loads((HERE / 'sweep-cases/index.json').read_text())
    stage = json.loads((HERE / 'proposals/cases.json').read_text())
    canonical = {case['case_id']: case for case in stage['cases']
                 if case['target_type'] == 'judgment_sweep'}
    for row in index['entries']:
        case_id = row['case_id']
        if case_id not in canonical:
            raise ValueError('Sweep construction not in canonical stage')
        construction = HERE / row['construction']
        log = construction.parent / 'offline.log'
        if sha(construction) != row['construction_sha256'] or not log.is_file():
            raise ValueError('Exact construction/offline proof changed')
        command = (' '.join((str(ROOT / '.venv-cpu/bin/python'),
                            str(ROOT / 'runtime.py'), 'offline', '--manifest',
                            str(HERE / 'sweep-cases/manifest.json'), '--case',
                            case_id, '--output',
                            str(ROOT / '.runtime-work/c229597-sweep-offline-v4' / case_id),
                            '--python', str(ROOT / '.venv-cpu/bin/python'))))
        manifest['cases'].append({
            'case_id': case_id, 'kind': 'delivery',
            'construction': row['construction'],
            'construction_sha256': row['construction_sha256'],
            'candidates': [],
            'candidate_risk': {'status': 'physical',
                               'reason': 'Original Native route, target realization and framing require review; fallback construction pending CPU proof.'},
            'offline': {'command': command, 'exit_code': 0,
                        'construction_sha256': row['construction_sha256'],
                        'log': str(log.relative_to(HERE)), 'log_sha256': sha(log)},
            'sweep_delivery_status': 'pending_compatibility_saved_physical_delivery_and_fallback_cpu_proofs',
            'native_executed': False, 'legal_verdict_claimed': False})
    if len(manifest['cases']) != 8:
        raise ValueError('Exact eight-case manifest differs')
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_cases': 8, 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

"""Run pinned offline checks for every current C229597 draft candidate."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
MANIFEST = P / 'draft-primary-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    records = []
    for case in manifest['cases']:
        group = case['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = (case if candidate == 'primary' else
                        next(x for x in case['candidates'] if x['id'] == candidate))
            construction = P / selected['construction']
            if sha(construction) != selected['construction_sha256']:
                raise ValueError('Construction changed: ' + group + '/' + candidate)
            destination = ROOT / '.runtime-work' / ('c229597-draft-v9-' + group + '-' + candidate)
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', case['case_id'],
                       '--candidate', candidate, '--output', str(destination)]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = P / ('draft-offline-' + group + '-' + candidate + '.log')
            log.write_text(run.stdout + run.stderr)
            if run.returncode:
                raise RuntimeError(group + '/' + candidate + ' offline failed: ' + run.stderr[-1000:])
            output = json.loads(run.stdout)
            if (output.get('offline_passed') is not True
                    or output.get('case_id') != case['case_id']
                    or output.get('candidate_id') != candidate
                    or output.get('simulation_started') is not False):
                raise ValueError('Offline receipt identity differs')
            records.append({'case_id': case['case_id'], 'candidate_id': candidate,
                            'construction_sha256': sha(construction),
                            'offline_log': log.name, 'offline_log_sha256': sha(log),
                            'materialized_log_sha256': sha(destination / 'offline.log'),
                            'offline_passed': True, 'native_executed': False})
    proof = {'format': 'c229597-draft-offline-matrix',
             'manifest_sha256': sha(MANIFEST), 'cases': len(manifest['cases']),
             'candidate_constructions_proven': len(records), 'records': records,
             'selected': False, 'delivery_ready': False}
    (P / 'draft-offline-index.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'cases': proof['cases'],
                      'candidate_constructions_proven': len(records)}))


if __name__ == '__main__':
    main()

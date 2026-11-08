"""Run all eight C146314 paragraph (c)(2) pinned offline candidates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    run = uuid.uuid4().hex[:12]
    entries = []
    manifest = HERE/'draft-execution-manifest.json'
    for witness in ('exception_3_1', 'exception_3_2'):
        case_id = CASE.name+'__'+witness
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            output = ROOT/'.runtime-work'/f'c146314-c2-{run}-{witness}-{candidate}'
            result = subprocess.run([sys.executable, str(ROOT/'runtime.py'), 'offline',
                                     '--manifest', str(manifest), '--case', case_id,
                                     '--candidate', candidate, '--output', str(output)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=330)
            if result.returncode:
                raise RuntimeError('paragraph (c)(2) pinned offline: '+result.stdout+result.stderr)
            response = json.loads(result.stdout)
            log = output/'offline.log'
            if not (response['offline_passed'] and
                    response['simulation_started'] is False and
                    'Ran 2 tests' in log.read_text() and '\nOK\n' in log.read_text()):
                raise ValueError('paragraph (c)(2) pinned receipt')
            selection = json.loads((output/'candidate-selection.json').read_text())
            entries.append({'case_id': case_id, 'candidate_id': candidate,
                            'construction_sha256': selection['construction_sha256'],
                            'materialized_dir': str(output.relative_to(ROOT)),
                            'log_sha256': sha(log), 'tests': 2, 'exit_code': 0,
                            'simulation_started': False})
    receipt = {'format': 'c146314-paragraph-c2-pinned-offline-v1',
               'manifest_sha256': sha(manifest), 'entries': entries,
               'passed': True, 'original_native_observed': False,
               'delivery_ready': False}
    (HERE/'offline/pinned-runtime-proof.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    p = prove()
    print(json.dumps({'passes': len(p['entries']),
                      'tests': sum(x['tests'] for x in p['entries'])}))

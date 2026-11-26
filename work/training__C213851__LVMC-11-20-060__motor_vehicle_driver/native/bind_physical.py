"""Run diagnostic physical outcome and capture lifecycle CPU probes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    summary = []
    for suffix in ('stop_before_sidewalk', 'cross_without_stop'):
        case = ROOT.name + '__' + suffix
        attempt = REPO / '.runtime-work' / (
            'c213851-saved-' + suffix + '-attempt')
        output = HERE / suffix / 'physical-proof'
        output.mkdir(parents=True, exist_ok=True)
        fixtures = []
        life = None
        for kind in ('complete_motion', 'incomplete_motion',
                     'missing_evidence', 'lifecycle'):
            command = [sys.executable, '-B', str(HERE / 'prove_physical.py'),
                       '--attempt', str(attempt), '--case', case,
                       '--kind', kind]
            run = subprocess.run(command, cwd=REPO, capture_output=True,
                                 text=True, env={**os.environ,
                                                'PYTHONDONTWRITEBYTECODE': '1'})
            if run.returncode:
                raise ValueError(kind + ': ' + run.stderr[-1000:])
            data = json.loads(run.stdout)
            result = output / (kind + '.json')
            result.write_text(json.dumps(data, indent=2) + '\n')
            log = output / (kind + '.log')
            log.write_text('exit_code=0\ncase_id=' + case + '\nkind=' + kind +
                           '\n')
            record = {'command': ' '.join(command),
                      'exit_code': 0,
                      'log': log.relative_to(ROOT).as_posix(),
                      'log_sha256': sha(log),
                      'result': result.relative_to(ROOT).as_posix(),
                      'result_sha256': sha(result)}
            if kind == 'lifecycle':
                life = {**data, 'command': record['command'],
                        'log': record['log'],
                        'log_sha256': record['log_sha256']}
            else:
                fixtures.append({'kind': kind, **record})
        receipt = output / 'receipt.json'
        receipt.write_text(json.dumps({
            'format': 'c213851-physical-preparation-cpu',
            'case_id': case,
            'construction_sha256': sha(HERE / suffix / 'construction.json'),
            'fixtures': fixtures,
            'lifecycle': life,
            'original_native_observed': False,
            'legal_verdict': None}, indent=2) + '\n')
        summary.append({'case_id': case,
                        'receipt': receipt.relative_to(ROOT).as_posix(),
                        'sha256': sha(receipt)})
    return summary


if __name__ == '__main__':
    print(json.dumps(bind()))

"""Run and bind roadway-return diagnostic physical/lifecycle probes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from build_entry_return import AID, POLICIES, ROOT


HERE = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    summary = []
    for policy in POLICIES:
        case = AID + '__' + policy
        attempt = REPO / '.runtime-work' / f'c213851-entry-compat-{policy}-caseconfig'
        output = HERE / 'entry_return' / policy / 'physical-proof'
        output.mkdir(parents=True, exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in ('complete_motion', 'incomplete_motion',
                     'missing_evidence', 'lifecycle'):
            command = [sys.executable, '-B', str(HERE / 'prove_entry_physical.py'),
                       '--attempt', str(attempt), '--case', case, '--kind', kind]
            run = subprocess.run(command, cwd=REPO, capture_output=True, text=True,
                                 env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if run.returncode:
                raise ValueError(kind + ': ' + run.stderr[-1000:])
            data = json.loads(run.stdout)
            result = output / (kind + '.json')
            result.write_text(json.dumps(data, indent=2) + '\n')
            log = output / (kind + '.log')
            log.write_text('exit_code=0\ncase_id=' + case + '\nkind=' + kind + '\n')
            row = {'command': ' '.join(command), 'exit_code': 0,
                   'log': log.relative_to(ROOT).as_posix(),
                   'log_sha256': sha(log),
                   'result': result.relative_to(ROOT).as_posix(),
                   'result_sha256': sha(result)}
            if kind == 'lifecycle':
                lifecycle = {**data, 'command': row['command'],
                             'log': row['log'], 'log_sha256': row['log_sha256']}
            else:
                fixtures.append({'kind': kind, **row})
        receipt = output / 'receipt.json'
        receipt.write_text(json.dumps({
            'format': 'c213851-entry-physical-preparation-cpu',
            'case_id': case,
            'construction_sha256': sha(HERE / 'entry_return' / policy /
                                       'construction.json'),
            'fixtures': fixtures, 'lifecycle': lifecycle,
            'original_native_observed': False, 'legal_verdict': None},
            indent=2) + '\n')
        summary.append({'case_id': case,
                        'receipt': receipt.relative_to(ROOT).as_posix(),
                        'sha256': sha(receipt)})
    return summary


if __name__ == '__main__':
    print(json.dumps(bind()))

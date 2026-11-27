"""Run and bind per-case synthetic physical/lifecycle CPU proofs."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

from red_curb import CASES
from run_proofs import MANIFEST, PYTHON, REPO, ROOT
from source_packet import ASSIGNMENT


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(value):
    return value.rstrip() + '\n' if value.strip() else ''


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c229452-physical-output'))
    for case, entry in zip(CASES, manifest['cases']):
        assert entry['case_id'] == ASSIGNMENT + '__' + case.name
        folder = ROOT / 'cases' / case.name / 'physical-fixtures'
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        life = None
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            result = folder / (kind + '-result.json')
            log = folder / (kind + '-test.log')
            command = [str(PYTHON), str(ROOT / 'prove_physical.py'), '--case', entry['case_id'],
                       '--fixture', kind, '--output', str(result)]
            process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
            log.write_text(clean(process.stdout + process.stderr))
            if process.returncode:
                raise ValueError('physical proof failed: ' + case.name + '/' + kind)
            if kind == 'lifecycle':
                life = {'events': json.loads(result.read_text())['events'], 'exit_code': 0,
                        'command': ' '.join(command), 'log': str(log.relative_to(ROOT)),
                        'log_sha256': sha(log)}
            else:
                fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                                 'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                                 'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result)})
        receipt = folder.parent / 'physical-preparation.json'
        receipt.write_text(json.dumps({'construction_sha256': entry['construction_sha256'],
                                       'fixtures': fixtures, 'lifecycle': life}, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

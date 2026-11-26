"""Run public positive and missing-source negative checks for all candidates."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-construction-manifest.json'
SCRATCH = ROOT / '.runtime-work/c24805-selected'
VALIDATOR = ROOT / '.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(line.rstrip() for line in
                                source.read_text().rstrip().splitlines()) + '\n')


def prove(case, candidate, existing=None):
    suffix = case.rsplit('__', 1)[1]
    destination = existing or SCRATCH / f'compat-{suffix}-{candidate}-{uuid.uuid4().hex[:8]}'
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'compatibility', '--manifest', str(MANIFEST.relative_to(ROOT)),
               '--case', case, '--candidate', candidate, '--output',
               str(destination.relative_to(ROOT)), '--library', 'runtime/library',
               '--validator', str(VALIDATOR.relative_to(ROOT))]
    if existing is None:
        env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
                   TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
        run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                             text=True, check=False)
        if run.returncode:
            raise RuntimeError(f'{suffix}/{candidate} compatibility failed: {run.stderr[-1800:]}')
    receipt = json.loads((destination / 'compatibility.json').read_text())
    if not receipt.get('passed') or receipt.get('case_id') != case or receipt.get('candidate_id') != candidate:
        raise ValueError('Public compatibility receipt failed identity or status')
    target = HERE / 'selected-compatibility' / f'{suffix}-{candidate}'
    for src, dst in (('compatibility.json', 'compatibility.json'),
                     ('compatibility-analysis.log', 'analysis.log'),
                     ('negative-analysis.log', 'negative.log')):
        copy_clean(destination / src, target / dst)
    return {'case_id': case, 'candidate_id': candidate,
            'receipt': str((target / 'compatibility.json').relative_to(HERE)),
            'receipt_sha256': sha(target / 'compatibility.json'),
            'analysis_sha256': sha(target / 'analysis.log'),
            'negative_sha256': sha(target / 'negative.log'),
            'positive_and_negative_passed': True,
            'source_output': str(destination.relative_to(ROOT))}


def main():
    cases = json.loads(MANIFEST.read_text())['cases']
    records = []
    first = SCRATCH / 'compat-probe-a-primary-v2'
    for entry in cases:
        for candidate in ('primary', 'fallback1'):
            reused = first if entry['case_id'].endswith('__probe_a') and candidate == 'primary' else None
            record = prove(entry['case_id'], candidate, reused)
            records.append(record)
            print(json.dumps({'case_id': record['case_id'],
                              'candidate_id': candidate,
                              'passed': True}), flush=True)
    target = HERE / 'selected-compatibility-proofs.json'
    target.write_text(json.dumps({'format': 'c24805-public-compatibility-proofs-v1',
                                  'proofs': records}, indent=2) + '\n')
    print(json.dumps({'proof_count': len(records), 'sha256': sha(target)},
                     sort_keys=True))


if __name__ == '__main__':
    main()

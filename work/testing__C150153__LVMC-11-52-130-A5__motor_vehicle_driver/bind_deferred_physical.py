"""Bind three synthetic physical checker outcomes to each selected exact case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from physical_outcomes import LIFECYCLE, verify_lifecycle

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'original_reviewed_site_required_at_capture':
        raise ValueError('physical CPU proofs require source-deferred production manifest')
    if not verify_lifecycle(LIFECYCLE):
        raise ValueError('Native lifecycle proof failed')
    lifecycle_log = HERE / 'cpu-physical-outcomes-tests.log'
    if not lifecycle_log.is_file() or 'test_lifecycle_requires_release_before_saved_processing' not in lifecycle_log.read_text():
        raise ValueError('lifecycle test log absent')
    for entry in manifest['cases']:
        kind = entry['case_id'].removeprefix(HERE.name + '__')
        fixtures = []
        for outcome_kind in KINDS:
            stem = 'cpu-deferred-physical-' + kind + '-' + outcome_kind
            result_path = HERE / (stem + '.json')
            log_path = HERE / (stem + '.log')
            command = [sys.executable, str(HERE / 'prove_physical_fixture.py'),
                       '--case', kind, '--kind', outcome_kind,
                       '--output', str(result_path)]
            env = dict(os.environ)
            env['PYTHONDONTWRITEBYTECODE'] = '1'
            env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c150153-owner/pipeline')
            env['TMPDIR'] = str(ROOT / '.runtime-work/c150153-owner/tmp')
            if result_path.exists() != log_path.exists():
                raise ValueError('incomplete physical fixture proof: ' + stem)
            if not result_path.exists():
                with log_path.open('w') as stream:
                    run = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                         stderr=subprocess.STDOUT, timeout=90)
                if run.returncode:
                    raise ValueError('physical fixture command failed: ' + stem)
            if 'status' not in log_path.read_text() or not result_path.is_file():
                raise ValueError('physical fixture proof absent: ' + stem)
            fixtures.append({'kind': outcome_kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': log_path.name,
                             'log_sha256': sha(log_path),
                             'result': result_path.name,
                             'result_sha256': sha(result_path)})
        receipt_path = HERE / ('cpu-deferred-physical-' + kind + '.json')
        proof = {'format': 'c150153-source-deferred-physical-cpu-proof',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures,
                 'lifecycle': {'events': LIFECYCLE, 'exit_code': 0,
                               'log': lifecycle_log.name,
                               'log_sha256': sha(lifecycle_log)},
                 'scope': 'synthetic physical checker and lifecycle only'}
        receipt_path.write_text(json.dumps(proof, indent=2) + '\n')
        entry['physical_preparation'] = {'receipt': receipt_path.name,
                                         'sha256': sha(receipt_path)}
        print(kind, 'three physical checker fixtures and lifecycle bound', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()

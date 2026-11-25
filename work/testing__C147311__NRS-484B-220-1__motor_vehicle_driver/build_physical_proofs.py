"""Bind three synthetic physical outcomes and saved lifecycle for four cases."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from one_way_direction import CASES

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/c147311-nov25e'
ASSIGNMENT = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(path: Path, output: str) -> None:
    path.write_text(output.rstrip() + '\n' if output.strip() else '', encoding='utf-8')


def main() -> None:
    manifest = json.loads((HERE / 'diagnostic-execution-manifest.json').read_text(encoding='utf-8'))
    by_id = {row['case_id']: row for row in manifest['cases']}
    env = dict(os.environ)
    env['PYTHONPATH'] = str(REPO / 'runtime') + os.pathsep + env.get('PYTHONPATH', '')
    if not env.get('SCENARIO_PIPELINE_OUTPUT_ROOT'):
        raise ValueError('export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first')
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.name
        attempt = SCRATCH / ('pinned-' + case.name + '-v12')
        saved = SCRATCH / ('saved-' + case.name + '-v12-receipt.json')
        if not saved.is_file() or not attempt.is_dir():
            raise ValueError('pinned selected compatibility/saved source absent: ' + case.name)
        folder = HERE / 'cases' / case.name
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = folder / ('physical-' + kind + '.json')
            if result.exists():
                result.unlink()
            log = folder / ('physical-' + kind + '.log')
            cmd = [sys.executable, str(HERE / 'prove_physical.py'),
                   '--case', case_id, '--kind', kind,
                   '--attempt', str(attempt), '--output', str(result)]
            ran = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
            clean_log(log, ran.stdout + ran.stderr)
            if ran.returncode:
                raise ValueError('physical fixture failed: ' + case.name + '/' + kind + ': ' + ran.stderr[-1000:])
            fixtures.append({'kind': kind, 'command': ' '.join(cmd),
                             'exit_code': 0,
                             'log': str(log.relative_to(HERE)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        life_log = folder / 'lifecycle.log'
        cmd = [sys.executable, str(HERE / 'prove_lifecycle.py'),
               '--case', case_id, '--attempt', str(attempt),
               '--saved-receipt', str(saved)]
        ran = subprocess.run(cmd, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
        clean_log(life_log, ran.stdout + ran.stderr)
        if ran.returncode:
            raise ValueError('lifecycle fixture failed: ' + case.name + ': ' + ran.stderr[-1000:])
        life = json.loads(ran.stdout)
        life.update({'command': ' '.join(cmd), 'log': str(life_log.relative_to(HERE)),
                     'log_sha256': sha(life_log)})
        receipt = {'format': 'c147311-diagnostic-physical-preparation-v1',
                   'case_id': case_id,
                   'construction_sha256': by_id[case_id]['construction_sha256'],
                   'fixtures': fixtures, 'lifecycle': life,
                   'source_kind': 'synthetic_software_fixture',
                   'physical_acceptance_claimed': False}
        (folder / 'physical-preparation.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        print(case.name, 'three physical outcomes and lifecycle passed')


if __name__ == '__main__':
    main()

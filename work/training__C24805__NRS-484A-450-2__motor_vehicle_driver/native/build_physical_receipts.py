"""Run physical fixture triads and Native closure order for exact cases."""

import hashlib
import json
import os
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
SCRIPT = HERE / 'prove-physical.py'
SCRATCH = ROOT / '.runtime-work/c24805-selected'
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    reports = []
    for suffix in ('probe_a', 'probe_b'):
        folder = HERE / 'physical-preparation' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        records = []
        for kind in KINDS:
            command = [str(ROOT / '.venv-cpu/bin/python'), str(SCRIPT),
                       '--sight', suffix, '--kind', kind]
            env = dict(os.environ,
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'physical-output'),
                       TMPDIR=str(SCRATCH),
                       PYTHONPATH=str(ROOT / 'runtime/scenario_pipeline'),
                       PYTHONDONTWRITEBYTECODE='1')
            run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                                 text=True, check=False)
            log = folder / f'{kind}.log'
            log.write_text('\n'.join(line.rstrip() for line in
                                     (run.stdout + run.stderr).rstrip().splitlines()) + '\n')
            if run.returncode:
                raise RuntimeError(f'Physical fixture failed {suffix}/{kind}: {log}')
            record = {'kind': kind, 'command': ' '.join(command),
                      'exit_code': 0, 'log': log.relative_to(HERE).as_posix(),
                      'log_sha256': sha(log)}
            if kind != 'lifecycle':
                result = folder / f'{kind}-result.json'
                record['result'] = result.relative_to(HERE).as_posix()
                record['result_sha256'] = sha(result)
            records.append(record)
        construction = HERE / f'selected-{suffix}-primary-construction.json'
        receipt = {'format': 'c24805-physical-preparation-v1',
                   'case_id': HERE.name + '__' + suffix,
                   'construction_sha256': sha(construction),
                   'fixtures': records[:3],
                   'lifecycle': {**records[3],
                                 'events': ['capture_finished', 'encoders_closed',
                                            'restoration_verified', 'native_exit',
                                            'owner_released', 'saved_processing_started']},
                   'physical_acceptance_claimed': False}
        target = folder / 'receipt.json'
        target.write_text(json.dumps(receipt, indent=2) + '\n')
        reports.append({'case_id': receipt['case_id'], 'receipt_sha256': sha(target)})
    print(json.dumps(reports, sort_keys=True))


if __name__ == '__main__':
    main()

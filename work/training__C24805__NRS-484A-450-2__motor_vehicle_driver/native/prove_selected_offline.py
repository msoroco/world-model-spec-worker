"""Run all four exact construction candidates through current-runtime offline."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-construction-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = ROOT / '.runtime-work/c24805-selected'
    scratch.mkdir(parents=True, exist_ok=True)
    output_root = scratch / 'pipeline-output'
    output_root.mkdir(exist_ok=True)
    proofs = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        for candidate in ('primary', 'fallback1'):
            destination = scratch / f'offline-{suffix}-{candidate}-{uuid.uuid4().hex[:8]}'
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'offline', '--manifest', str(MANIFEST.relative_to(ROOT)),
                       '--case', entry['case_id'], '--candidate', candidate,
                       '--output', str(destination.relative_to(ROOT)),
                       '--python', str(ROOT / '.venv-cpu/bin/python')]
            env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(output_root),
                       TMPDIR=str(scratch), PYTHONDONTWRITEBYTECODE='1')
            run = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                 capture_output=True, check=False)
            log = HERE / f'selected-{suffix}-{candidate}-offline.log'
            lines = (run.stdout + run.stderr).rstrip().splitlines()
            log.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
            if run.returncode or not json.loads(run.stdout)['offline_passed']:
                raise RuntimeError(f'Exact offline failed: {suffix} {candidate}: {log}')
            expected_sha = (entry['construction_sha256'] if candidate == 'primary'
                            else entry['candidates'][0]['construction_sha256'])
            proofs.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                           'construction_sha256': expected_sha,
                           'command': ' '.join(command), 'exit_code': run.returncode,
                           'log': log.relative_to(HERE).as_posix(),
                           'log_sha256': sha(log)})
    target = HERE / 'selected-offline-proofs.json'
    target.write_text(json.dumps({'format': 'c24805-selected-offline-proofs-v1',
                                  'runtime_manifest_sha256':
                                  manifest['runtime_manifest_sha256'],
                                  'proofs': proofs}, indent=2) + '\n')
    print(json.dumps({'proof_count': len(proofs), 'sha256': sha(target)},
                     sort_keys=True))


if __name__ == '__main__':
    main()

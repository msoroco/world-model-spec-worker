"""Prove saved-only analysis against copies of exact CPU attempts."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/lvmc305-saved-v1'
SOURCE = REPO / '.runtime-work/lvmc305-proofs-v1'
PYTHON = REPO / '.venv-cpu/bin/python'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'mpl').mkdir(exist_ok=True)
    (SCRATCH / 'pipeline-output').mkdir(exist_ok=True)
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(SCRATCH),
                       SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline-output'),
                       MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = SOURCE / (suffix + '-primary/compat')
        attempt = SCRATCH / (suffix + '-attempt')
        if attempt.exists():
            shutil.rmtree(attempt)
        shutil.copytree(source, attempt)
        selection = attempt / 'candidate-selection.json'
        if selection.exists():
            selection.unlink()
        output = SCRATCH / (suffix + '-output')
        command = [str(PYTHON), str(REPO / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(output),
                   '--library', str(REPO / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        completed = subprocess.run(command, cwd=REPO, env=environment,
                                   capture_output=True, text=True)
        log = ROOT / ('cpu-saved-' + suffix + '.log')
        log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
        if completed.returncode:
            raise RuntimeError(suffix + ': ' + log.read_text()[-1500:])
        proof = json.loads((output / 'v0001/processing.json').read_text())
        if (proof['passed'] is not True or proof['recorded_only'] is not True or
                proof['case_id'] != entry['case_id'] or not proof['originals_preserved'] or
                proof['missing_evidence']):
            raise ValueError('Saved-only proof did not complete: ' + suffix)
        entry['post_capture'] = {'recorded_only': True, 'command': ' '.join(command),
                                 'feedback_command': ' '.join(command),
                                 'test_exit_code': 0, 'test_log': log.name,
                                 'test_log_sha256': sha(log)}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(suffix, 'passed', flush=True)


if __name__ == '__main__':
    run()

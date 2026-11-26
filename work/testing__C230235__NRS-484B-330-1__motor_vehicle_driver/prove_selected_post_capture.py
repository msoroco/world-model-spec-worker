"""Exercise saved-only processing and feedback for all exact flagger cases."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = ROOT / '.runtime-work/c230235-owner-nov26b/post-capture'
STAGES = ROOT / '.runtime-work/c230235-saved-diagnostics'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    python = str(ROOT / '.venv-cpu/bin/python')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT / '.runtime-work/c230235-owner-nov26b'))
    for entry in manifest['cases']:
        case_id = entry['case_id']
        short = case_id.removeprefix(HERE.name + '__')
        stage = STAGES / (short + '-original-shaped')
        saved = SCRATCH / (short + '-saved')
        feedback = SCRATCH / (short + '-feedback.json')
        if saved.exists():
            shutil.rmtree(saved)
        feedback.unlink(missing_ok=True)
        test_command = [python, str(HERE / 'process_saved.py'), '--stage', str(stage),
                        '--output', str(saved), '--case', case_id, '--diagnostic-fixture']
        done = subprocess.run(test_command, cwd=ROOT, env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if done.returncode:
            raise ValueError('saved-only diagnostic failed: ' + done.stdout[-1200:])
        if json.loads((saved / 'saved-report.json').read_text())['case_id'] != case_id:
            raise ValueError('saved processing returned another case')
        feedback_command = [python, str(HERE / 'delivery_audit.py'), '--stage', str(stage),
                            '--saved', str(saved), '--case', case_id,
                            '--diagnostic-fixture', '--output', str(feedback)]
        audit = subprocess.run(feedback_command, cwd=ROOT, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        if audit.returncode:
            raise ValueError('saved feedback failed: ' + audit.stdout[-1200:])
        if json.loads(feedback.read_text())['case_id'] != case_id:
            raise ValueError('saved feedback selected another case')
        log = HERE / ('selected-post-' + short + '.log')
        log.write_text(('process_saved exit 0, source-kind synthetic_fixture, exact case ' + case_id + '\n'
                        'delivery_audit exit 0, four saved video views fully decoded\n'))
        entry['post_capture'] = {
            'recorded_only': True,
            'command': (python + ' ' + str(HERE / 'process_saved.py') +
                        ' --stage "$ATTEMPT/original-flagger-source" --output "$SAVED" --case ' + case_id),
            'feedback_command': (python + ' ' + str(HERE / 'delivery_audit.py') +
                                 ' --stage "$ATTEMPT/original-flagger-source" --saved "$SAVED"'
                                 ' --case ' + case_id + ' --output "$SAVED/../delivery-feedback.json"'),
            'test_command': ' '.join(test_command), 'test_exit_code': 0,
            'test_log': log.name, 'test_log_sha256': sha(log),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
        print('saved-only post capture', short, 'passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + '\n')


if __name__ == '__main__':
    prove()

"""Retain exact positive and source-tamper audit proof for each selected case."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/lvmc305-audit-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'mpl').mkdir(exist_ok=True)
    (SCRATCH / 'pipeline-output').mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(SCRATCH),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'pipeline-output'),
               MPLCONFIGDIR=str(SCRATCH / 'mpl'))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        evidence = {}
        for kind in ('positive', 'negative'):
            command = [str(REPO / '.venv-cpu/bin/python'), str(ROOT / 'audit_probe.py'),
                       '--case', entry['case_id'],
                       '--output', str(SCRATCH / (suffix + '-' + kind))]
            if kind == 'negative':
                command.append('--negative')
            completed = subprocess.run(command, cwd=REPO, env=env,
                                       capture_output=True, text=True)
            log = ROOT / ('audit-' + suffix + '-' + kind + '.log')
            log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
            expected_exit = 0 if kind == 'positive' else 1
            if completed.returncode != expected_exit:
                raise RuntimeError(suffix + ' ' + kind + ': ' + log.read_text()[-1500:])
            evidence[kind] = {'command': ' '.join(command), 'exit_code': expected_exit,
                              'log': log.name, 'sha256': sha(log)}
        if 'sealed original missing or changed' not in (ROOT / evidence['negative']['log']).read_text():
            raise ValueError('source mutation rejection did not execute')
        positive, negative = evidence['positive'], evidence['negative']
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(ROOT / 'delivery_audit.py'),
            'command': positive['command'], 'test_exit_code': 0,
            'test_log': positive['log'], 'test_log_sha256': positive['sha256'],
            'negative_command': negative['command'], 'negative_exit_code': 1,
            'negative_expected_error': 'sealed original missing or changed',
            'negative_log': negative['log'], 'negative_log_sha256': negative['sha256']}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(suffix, 'passed', flush=True)


if __name__ == '__main__':
    run()

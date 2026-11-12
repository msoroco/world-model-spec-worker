"""Reexecute all independent delivery audits after shared auditor changes."""

import json
from hashlib import sha256
from pathlib import Path
import os
import shlex
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(command):
    parts = shlex.split(command)
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'runtime/scenario_pipeline'))
    if parts and parts[0].startswith('PYTHONPATH='):
        env['PYTHONPATH'] = str(ROOT / parts.pop(0).split('=', 1)[1])
    return subprocess.run(parts, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        acceptance = entry['delivery_acceptance']
        acceptance['script_sha256'] = digest(HERE / acceptance['script'])
        for negative, command_key, log_key, hash_key, exit_key in (
            (False, 'command', 'test_log', 'test_log_sha256', 'test_exit_code'),
            (True, 'negative_command', 'negative_log', 'negative_log_sha256', 'negative_exit_code'),
        ):
            result = run(acceptance[command_key])
            log = HERE / acceptance[log_key]
            log.write_text(result.stdout)
            if negative:
                if result.returncode == 0 or acceptance['negative_expected_error'] not in result.stdout:
                    raise ValueError('Negative delivery audit failed: ' + entry['case_id'])
            elif result.returncode:
                raise ValueError('Positive delivery audit failed: ' + entry['case_id'])
            acceptance[hash_key] = digest(log)
            acceptance[exit_key] = result.returncode
        print(entry['case_id'], 'delivery positive and negative passed', flush=True)
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

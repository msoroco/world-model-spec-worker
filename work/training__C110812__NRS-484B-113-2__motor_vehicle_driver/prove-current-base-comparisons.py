"""Run positive and negative exact-case CPU comparison audits."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for stem, script in (('current-base-comparison', 'audit-selected-comparison.py'),
                         ('current-base-control-comparison', 'audit-control-comparison.py')):
        rows = []
        for label, arg, expected in (('positive', None, 0),
                                     ('negative-drift', '--reject-comparison-drift', 1),
                                     ('negative-source', '--remove-native-source', 1)):
            log = HERE / f'{stem}-{label}.log'
            command = [sys.executable, str(HERE / script)] + ([arg] if arg else [])
            with log.open('w') as output:
                status = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT).returncode
            if status != expected:
                raise ValueError(f'{stem} {label}: exit {status}, expected {expected}: {log}')
            rows.append({'label': label, 'exit_code': status, 'log': log.name, 'sha256': sha(log)})
        result = {'format': 'c110812-current-base-comparison-proof',
                  'script': script, 'script_sha256': sha(HERE / script), 'rows': rows,
                  'scope': 'synthetic CPU source comparison; no original Native outcome'}
        (HERE / (stem + '-proof.json')).write_text(json.dumps(result, indent=2) + '\n')
        print(stem, 'positive and negative audits passed')


if __name__ == '__main__':
    main()

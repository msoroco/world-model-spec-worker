"""Run independent positive and missing-original-source delivery audit tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = ('witness_1', 'witness_2', 'extreme_right_1', 'extreme_right_2')
EXPECTED = 'Missing original source: exact original Native result'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = []
    for suffix in CASES:
        case = HERE.name + '__' + suffix
        command = [sys.executable, str(HERE / 'delivery_audit.py'), '--case', case, '--self-test']
        paths = []
        for negative in (False, True):
            cmd = command + (['--negative'] if negative else [])
            run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=30)
            log = HERE / 'delivery-proofs' / (suffix + ('-negative.log' if negative else '-positive.log'))
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text('\n'.join(line.rstrip() for line in (run.stdout + run.stderr).splitlines()).rstrip() + '\n')
            if (run.returncode == 0) == negative or (negative and EXPECTED not in log.read_text()):
                raise ValueError('Delivery audit self-test differs: ' + suffix)
            paths.append({'command': ' '.join(cmd), 'exit_code': run.returncode,
                          'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log)})
        records.append({'case_id': case, 'positive': paths[0], 'negative': paths[1]})
        print(suffix, 'positive and negative passed', flush=True)
    proof = HERE / 'delivery-proofs/proof.json'
    proof.write_text(json.dumps({'records': records, 'physical_claimed': False}, indent=2) + '\n')


if __name__ == '__main__':
    main()

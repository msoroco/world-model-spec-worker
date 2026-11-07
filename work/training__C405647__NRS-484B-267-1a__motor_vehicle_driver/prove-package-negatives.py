"""Retain the exact missing-source failure from each prior synthetic package."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import execution_env


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    output = HERE / 'draft-package-negatives'
    output.mkdir(exist_ok=True)
    rows = []
    for case in ('witness_1', 'witness_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            label = ('draft-package-probe.log' if (case, candidate) == ('witness_1', 'primary')
                     else f'draft-package-{case}-{candidate}.log')
            log = HERE / label
            first, encoded = log.read_text().splitlines()
            scratch = Path(first.removeprefix('scratch '))
            negative = scratch / 'negative'
            assert negative.is_dir() and not (negative / 'source-scope.json').exists()
            failure = subprocess.run(
                [sys.executable, str(negative / 'finalize.py'), '--attempt', str(negative),
                 '--output', str(negative / 'analysis-report-recheck.json')],
                cwd=negative, env=execution_env(), text=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
            expected = 'Missing required source: source-scope.json'
            if failure.returncode == 0 or expected not in failure.stdout:
                raise ValueError(f'{case}/{candidate}: negative rejected for another cause')
            retained = output / f'{case}-{candidate}.log'
            retained.write_text(failure.stdout)
            result = json.loads(encoded)
            result['negative'] = {'removed': 'source-scope.json',
                                  'exit_code': failure.returncode,
                                  'log_sha256': sha(retained)}
            log.write_text(first + '\n' + json.dumps(result) + '\n')
            rows.append({'case_id': result['case_id'], 'candidate_id': candidate,
                         'negative_log': str(retained.relative_to(HERE)),
                         'negative_log_sha256': sha(retained),
                         'expected_error': expected})
    proof = {'passed': True, 'negative_count': len(rows), 'rows': rows}
    (HERE / 'draft-package-negative-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))

"""Run exact bundled finalizers on source-shaped positive and missing-source fixtures."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from prove_sidewalk import fixture

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
AID = HERE.parent.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_finalizer(attempt):
    return subprocess.run(
        [sys.executable, str(attempt / 'native/finalize.py'),
         '--attempt', str(attempt),
         '--output', str(attempt / 'analysis-report.json')],
        cwd=attempt, env=os.environ, capture_output=True, text=True,
        timeout=120)


def prove():
    from worker_exchange.runtime_cli import materialize
    from worker_exchange.measurement_contract import verify_report
    manifest = HERE / 'probe-offline-manifest.json'
    outcomes = []
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work',
                                     prefix='c213851-finalizer-') as tmp:
        root = Path(tmp)
        for suffix in ('stop_before_sidewalk', 'cross_without_stop'):
            case_id = AID + '__' + suffix
            positive = root / (suffix + '-positive')
            materialize(manifest, case_id, positive)
            fixture(positive, suffix)
            success = run_finalizer(positive)
            if success.returncode:
                raise AssertionError(success.stdout + success.stderr)
            report = json.loads((positive / 'analysis-report.json').read_text())
            result = json.loads((positive / 'result.json').read_text())
            contract = json.loads((HERE / suffix /
                                   'measurement-contract.json').read_text())
            verified = verify_report(contract, report, positive)
            if (report.get('source_complete') is not True or
                    report.get('physical_or_legal_acceptance') is not False or
                    result.get('accepted') is not False or len(verified) != 2):
                raise AssertionError('Diagnostic fixture claimed physical acceptance')
            negative = root / (suffix + '-negative')
            materialize(manifest, case_id, negative)
            fixture(negative, suffix)
            (negative / 'site-sources/sidewalk.json').unlink()
            failure = run_finalizer(negative)
            if (failure.returncode == 0 or
                    'Missing required source: site-sources/sidewalk.json' not in
                    failure.stdout + failure.stderr):
                raise AssertionError('Missing original sidewalk source accepted: ' +
                                     failure.stdout + failure.stderr)
            outcomes.append({
                'case_id': case_id,
                'positive_exit_code': success.returncode,
                'negative_exit_code': failure.returncode,
                'negative_error':
                    'Missing required source: site-sources/sidewalk.json',
                'analysis_report_sha256': sha(positive / 'analysis-report.json'),
                'native_result_sha256': sha(positive / 'result.json'),
                'source_shape_fixture_only': True,
            })
    proof = {'format': 'c213851-bundled-finalizer-source-shape-proof',
             'passed': True, 'outcomes': outcomes,
             'original_capture_observed': False,
             'physical_or_legal_acceptance': False}
    path = HERE / 'finalizer-source-shape-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    return {'passed': True, 'cases': len(outcomes),
            'proof_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(prove()))

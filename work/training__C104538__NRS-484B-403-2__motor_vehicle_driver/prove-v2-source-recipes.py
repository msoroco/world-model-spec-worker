"""Exercise current recipe sources through exact draft saved finalizers."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import execution_env, materialize
from worker_exchange.saved_processing import copy_sources, prepare_video


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case):
    fixture = ROOT / '.runtime-work/c104538-v2' / f'fixture-final-{case}'
    output = ROOT / '.runtime-work/c104538-v2' / f'finalizer-{case}'
    if output.exists():
        shutil.rmtree(output)
    case_id = HERE.name + '__' + case
    materialize(HERE / 'draft-execution-manifest.json', case_id, output)
    copy_sources(fixture, output)
    prepare_video(output)
    original = {name: sha(output / name) for name in
                ('native_samples.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                 'sign-review.json', 'approach.mkv')}
    command = [sys.executable, str(output / 'finalize.py'), '--attempt', str(output),
               '--output', str(output / 'analysis-report.json')]
    subprocess.run(command, cwd=output, env=execution_env(), check=True,
                   capture_output=True, text=True, timeout=300)
    report = json.loads((output / 'analysis-report.json').read_text())
    observed = report['measurements']['signed_u_turn']['value'][
        'u_turn_within_governed_region_observed']
    assert observed == (case == 'witness_2')
    assert len((output / 'channels/dev.governs.jsonl').read_text().splitlines()) == 600
    assert all(sha(output / name) == digest for name, digest in original.items())
    required = output / 'capture/evidence.jsonl'
    hidden = output / 'capture/evidence.hidden'
    required.rename(hidden)
    try:
        failure = subprocess.run(command, cwd=output, env=execution_env(),
                                 capture_output=True, text=True, timeout=300)
        assert failure.returncode != 0
        assert 'Missing required source: evidence.jsonl' in failure.stdout + failure.stderr
    finally:
        hidden.rename(required)
    return {'case': case, 'case_id': case_id, 'frames': 600,
            'signed_u_turn': observed,
            'analysis_sha256': sha(output / 'analysis-report.json'),
            'missing_evidence_rejected': True,
            'scope': 'synthetic diagnostic raw-source finalization only'}


if __name__ == '__main__':
    print(json.dumps([run(case) for case in ('witness_1', 'witness_2')], indent=2))

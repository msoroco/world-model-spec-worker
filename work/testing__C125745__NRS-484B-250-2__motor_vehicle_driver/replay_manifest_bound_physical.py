"""Replay retained physical CPU diagnostics before rebinding manifest hashes."""
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = (
    'frame24_fallback1_physical_cpu_diagnostics',
    'frame24_fallback2_physical_cpu_diagnostics',
    'frame24_fallback3_physical_cpu_diagnostics',
    'frame32_fallback1_physical_cpu_diagnostics',
    'frame32_fallback2_physical_cpu_diagnostics',
    'frame40_fallback2_physical_cpu_diagnostics',
    'frame40_fallback3_physical_cpu_diagnostics',
)


def sha(value):
    return hashlib.sha256(value).hexdigest()


def replay(proof, name, kind):
    tokens = shlex.split(proof['command'])
    env = os.environ.copy()
    while tokens and '=' in tokens[0] and not tokens[0].startswith('.'):
        key, value = tokens.pop(0).split('=', 1)
        if key not in ('SCENARIO_PIPELINE_OUTPUT_ROOT', 'PYTHONDONTWRITEBYTECODE'):
            raise ValueError('Unexpected command environment')
        env[key] = value.replace('$PWD', str(ROOT))
    if tokens[:2] != ['.venv-cpu/bin/python',
                      'work/' + HERE.name + '/physical_motion_fixture.py']:
        raise ValueError('Unexpected proof command')
    if '--output' not in tokens:
        raise ValueError('Missing physical fixture output')
    output = (ROOT / tokens[tokens.index('--output') + 1]).resolve()
    if ROOT / '.runtime-work' not in output.parents:
        raise ValueError('Fixture output outside ignored work')
    output.parent.mkdir(parents=True, exist_ok=True)
    run = subprocess.run(tokens, cwd=ROOT, env=env, text=True,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         timeout=90)
    if run.returncode != 0:
        raise ValueError(name + '/' + kind + ' failed: ' + run.stdout[-1000:])
    data = output.read_bytes()
    expected = proof.get('result_sha256', proof.get('receipt_sha256'))
    if sha(data) != expected:
        raise ValueError(name + '/' + kind + ' result differs from retained proof')
    log = run.stdout.encode()
    if proof.get('log_sha256') and sha(log) != proof['log_sha256']:
        raise ValueError(name + '/' + kind + ' stdout differs from retained proof')
    return {'kind': kind, 'result_sha256': sha(data), 'stdout_sha256': sha(log)}


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    manifest_sha = sha((HERE / 'execution-manifest.json').read_bytes())
    results = {}
    for name in NAMES:
        spec = plan[name]
        results[name] = [replay(proof, name, kind)
                         for kind, proof in spec['proofs'].items()]
    for name in NAMES:
        spec = plan[name]
        spec['previous_qualitative_selection_manifest_sha256'] = spec['manifest_sha256']
        spec['manifest_sha256'] = manifest_sha
        spec['qualitative_selection_replay_20261124'] = results[name]
    plan_path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'manifest_sha256': manifest_sha,
                      'replayed': sum(map(len, results.values())),
                      'plans': list(results)}, sort_keys=True))


if __name__ == '__main__':
    main()

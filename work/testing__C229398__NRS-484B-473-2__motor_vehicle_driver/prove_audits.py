"""Run independent positive/negative delivery and five comparison CPU audits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from source_packet import ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PLAN = HERE / 'case-plan.json'
SCRATCH = ROOT / '.runtime-work/c229398-independent-audits'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def run(command, env):
    return subprocess.run(command, cwd=ROOT, env=env,
                          capture_output=True, text=True)


def log(name, result):
    path = HERE / name
    path.write_text((result.stdout + result.stderr).rstrip() + '\n')
    return path


def prove():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c229398-output')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c229398-tmp')
    Path(env['SCENARIO_PIPELINE_OUTPUT_ROOT']).mkdir(parents=True, exist_ok=True)
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case_id = entry['case_id']
        name = case_id.removeprefix(ASSIGNMENT + '__')
        attempt = ROOT / '.runtime-work/c229398-selected-compat' / name / 'primary'
        output = SCRATCH / (name + '-delivery.json')
        if output.exists():
            output.unlink()
        command = [str(ROOT / '.venv-cpu/bin/python'),
                   str(HERE / 'delivery_acceptance.py'),
                   '--case-id', case_id, '--attempt', str(attempt),
                   '--plan', str(PLAN), '--output', str(output)]
        done = run(command, env)
        positive_log = log('cpu-delivery-' + name + '.log', done)
        if done.returncode or not json.loads(output.read_text())['four_view_full_decode']:
            raise ValueError('positive independent delivery audit failed: ' +
                             positive_log.read_text()[-1500:])
        missing = SCRATCH / (name + '-missing')
        if missing.exists():
            shutil.rmtree(missing)
        shutil.copytree(attempt, missing)
        (missing / 'parking_lawfulness.txt').unlink()
        negative_output = SCRATCH / (name + '-negative.json')
        if negative_output.exists():
            negative_output.unlink()
        negative = command.copy()
        negative[negative.index('--attempt') + 1] = str(missing)
        negative[negative.index('--output') + 1] = str(negative_output)
        failed = run(negative, env)
        negative_log = log('cpu-delivery-' + name + '-negative.log', failed)
        expected = 'Missing required source: parking_lawfulness.txt'
        if failed.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError('missing parked-lawfulness source not rejected: ' + name)
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['full-test'],
            'checks': CHECKS, 'script': 'delivery_acceptance.py',
            'script_sha256': sha(HERE / 'delivery_acceptance.py'),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': positive_log.name,
            'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative),
            'negative_exit_code': failed.returncode,
            'negative_expected_error': expected,
            'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log),
            'diagnostic_fixture': True, 'physical_acceptance_claimed': False}
    write(MANIFEST, manifest)
    plan = json.loads(PLAN.read_text())
    comparisons = []
    for comparison in plan['comparisons']:
        name = comparison['comparison_id']
        attempts = [ROOT / '.runtime-work/c229398-selected-compat' /
                    case_id.removeprefix(ASSIGNMENT + '__') / 'primary'
                    for case_id in comparison['case_ids']]
        output = SCRATCH / (name + '-comparison.json')
        if output.exists():
            output.unlink()
        command = [str(ROOT / '.venv-cpu/bin/python'),
                   str(HERE / 'comparison_acceptance.py'),
                   '--comparison', name,
                   '--comparison-id', ASSIGNMENT + '__' + name,
                   '--plan', str(PLAN)]
        for attempt in attempts:
            command.extend(['--attempt', str(attempt)])
        command.extend(['--output', str(output)])
        done = run(command, env)
        audit_log = log('cpu-comparison-' + name + '.log', done)
        if done.returncode:
            raise ValueError('independent comparison audit failed: ' +
                             audit_log.read_text()[-1500:])
        comparisons.append({'comparison_id': name,
                            'case_ids': comparison['case_ids'],
                            'audit': {'script': 'comparison_acceptance.py',
                                      'script_sha256': sha(HERE / 'comparison_acceptance.py'),
                                      'command': ' '.join(command),
                                      'test_exit_code': 0,
                                      'test_log': audit_log.name,
                                      'test_log_sha256': sha(audit_log),
                                      'result_sha256': sha(output),
                                      'diagnostic_fixture': True,
                                      'physical_acceptance_claimed': False}})
    write(HERE / 'comparison-audits.json', {
        'format': 'worker-comparison-audits', 'assignment_id': ASSIGNMENT,
        'comparisons': comparisons})
    return len(manifest['cases']), len(comparisons)


if __name__ == '__main__':
    print(prove())

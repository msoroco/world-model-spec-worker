"""Run independent CPU delivery and six comparison audits for exact selected cases."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / 'native'
SCRATCH = REPO / '.runtime-work/c200568-audits'
SCRATCH.mkdir(exist_ok=True)
PYTHON = REPO / '.venv-cpu/bin/python'
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def execute(command, log):
    result = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    script = ROOT / 'delivery_audit.py'
    base = [str(PYTHON), str(script)]
    proofs = {}
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        attempt = REPO / ('.runtime-work/c200568-reproof-v3-primary-compat-' + suffix)
        processing = ROOT / ('native/selected-' + suffix + '-saved-processing.json')
        output = SCRATCH / (suffix + '-delivery.json')
        command = base + ['--case', case, '--candidate', 'primary', '--attempt', str(attempt),
                          '--processing', str(processing), '--output', str(output), '--diagnostic']
        positive_log = NATIVE / ('selected-' + suffix + '-delivery-positive.log')
        negative_log = NATIVE / ('selected-' + suffix + '-delivery-negative.log')
        positive = execute(command, positive_log)
        negative_command = command + ['--omit-source', 'hydrant_survey.json']
        negative = execute(negative_command, negative_log)
        if positive != 0 or negative == 0 or 'Missing source: hydrant_survey.json' not in negative_log.read_text():
            raise ValueError('Delivery audit failed: ' + suffix + ' ' + str((positive, negative)))
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion', 'independent_hydrant_review'],
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(command[:-1] + ['--diagnostic']),
            'test_log': str(positive_log.relative_to(ROOT)), 'test_log_sha256': sha(positive_log),
            'test_exit_code': 0, 'negative_command': ' '.join(negative_command),
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': sha(negative_log), 'negative_exit_code': negative,
            'negative_expected_error': 'Missing source: hydrant_survey.json'}
        proofs[case] = (processing, output)
        print('delivery', suffix, flush=True)
    comparison_script = ROOT / 'comparison_audit.py'
    for comparison in plan['comparisons']:
        comparison_id = comparison['comparison_id']
        name = comparison_id.split('__')[-1]
        command = [str(PYTHON), str(comparison_script), '--comparison-id', comparison_id]
        for label, case in zip('abc', comparison['case_ids']):
            processing, audit = proofs[case]
            command += ['--' + label + '-processing', str(processing),
                        '--' + label + '-audit', str(audit)]
        command += ['--output', str(SCRATCH / (name + '-comparison.json')), '--diagnostic']
        positive_log = NATIVE / (name + '-comparison-positive.log')
        negative_log = NATIVE / (name + '-comparison-negative.log')
        positive = execute(command, positive_log)
        negative_command = command + ['--omit-b-audit']
        negative = execute(negative_command, negative_log)
        if positive != 0 or negative == 0 or 'Missing independent B audit' not in negative_log.read_text():
            raise ValueError('Comparison audit failed: ' + name + ' ' + str((positive, negative)))
        record = {'script': 'comparison_audit.py', 'script_sha256': sha(comparison_script),
                  'positive_log': str(positive_log.relative_to(ROOT)),
                  'positive_log_sha256': sha(positive_log),
                  'negative_log': str(negative_log.relative_to(ROOT)),
                  'negative_log_sha256': sha(negative_log)}
        for entry in manifest['cases']:
            if entry['case_id'] in comparison['case_ids']:
                entry['comparison_audit'] = record
        print('comparison', name, flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'cases': len(proofs),
                      'comparisons': len(plan['comparisons'])}))


if __name__ == '__main__':
    main()

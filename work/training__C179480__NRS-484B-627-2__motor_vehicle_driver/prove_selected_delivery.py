"""Run independent positive and missing-source CPU audits for selected cases."""
import hashlib
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'audit_selected_delivery.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    if manifest.get('remaining_cpu_proofs'):
        raise ValueError('Selected compatibility matrix is incomplete')
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c179480-delivery-audit')
    for entry in manifest['cases']:
        case = entry['case_id']
        if not entry.get('saved_processing') or any(
                not candidate.get('saved_processing') for candidate in entry['candidates']):
            raise ValueError('Selected saved-processing matrix is incomplete: ' + case)
        prefix = case.removeprefix(HERE.name + '__')
        logs = []
        for negative in (False, True):
            args = [sys.executable, str(SCRIPT), '--case', case]
            if negative:
                args.append('--remove-native-source')
            process = subprocess.run(args, cwd=ROOT, env=env,
                                     text=True, capture_output=True, check=False)
            log = HERE / f'selected-delivery-{prefix}-{ "negative" if negative else "positive"}.log'
            log.write_text(process.stdout + process.stderr)
            if negative:
                if process.returncode == 0 or 'Missing required source: native-actors.jsonl' not in log.read_text():
                    raise ValueError('Missing-source delivery audit did not reject: ' + case)
            else:
                if process.returncode != 0:
                    raise ValueError('Positive delivery source audit failed: ' + case)
                result = json.loads(process.stdout)
                if result['case_id'] != case or not result['passed'] or result['accepted'] or not set(CHECKS) <= set(result['checks']):
                    raise ValueError('Independent delivery audit returned wrong scope: ' + case)
            logs.append((args, process.returncode, log))
        positive, negative = logs
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': shlex.join(positive[0]),
            'test_exit_code': positive[1], 'test_log': positive[2].name,
            'test_log_sha256': sha(positive[2]),
            'negative_command': shlex.join(negative[0]),
            'negative_exit_code': negative[1],
            'negative_expected_error': 'Missing required source: native-actors.jsonl',
            'negative_log': negative[2].name,
            'negative_log_sha256': sha(negative[2]),
            'scope': 'synthetic CPU source and receipt proof; Native and legal acceptance remain local'}
        print('PASS', case, flush=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print('MANIFEST', sha(path), flush=True)


if __name__ == '__main__':
    run()

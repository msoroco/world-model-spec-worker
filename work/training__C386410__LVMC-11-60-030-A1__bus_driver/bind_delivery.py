"""Bind independent original-only delivery audit positive-inventory/negative-source tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRIPT = ROOT / 'delivery_audit.py'
MANIFEST = ROOT / 'execution-manifest.json'
ERROR = 'Synthetic fixture cannot establish original Native delivery'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = REPO / '.runtime-work/c386410-delivery'
    scratch.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch))
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        proof = ROOT / 'proofs' / suffix
        proof.mkdir(parents=True, exist_ok=True)
        commands = []
        for negative in (False, True):
            args = [sys.executable, '-B', str(SCRIPT), '--case', entry['case_id'], '--selftest']
            if negative:
                args.append('--negative-fixture')
            run = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True)
            log = proof / ('delivery-negative.log' if negative else 'delivery-positive.log')
            log.write_text(run.stdout + run.stderr)
            if (negative and (run.returncode == 0 or ERROR not in log.read_text())) or (not negative and run.returncode != 0):
                raise RuntimeError('Delivery selftest failure: ' + suffix)
            commands.append((' '.join(args), run.returncode, log))
        positive, negative = commands
        entry['delivery_acceptance'] = {'case_id': entry['case_id'], 'sets': ['full-train'],
            'checks': CHECKS, 'script': 'delivery_audit.py', 'script_sha256': sha(SCRIPT),
            'command': positive[0], 'test_exit_code': 0,
            'test_log': str(positive[2].relative_to(ROOT)), 'test_log_sha256': sha(positive[2]),
            'negative_command': negative[0], 'negative_exit_code': negative[1],
            'negative_expected_error': ERROR,
            'negative_log': str(negative[2].relative_to(ROOT)),
            'negative_log_sha256': sha(negative[2])}
        print('delivery CPU proof', suffix, flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

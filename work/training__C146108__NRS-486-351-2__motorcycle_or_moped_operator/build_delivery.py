"""Bind independent motorcycle original-source delivery audit selftests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SCRATCH = ROOT.parents[1] / '.runtime-work/c146108-moto'
SCRIPT = ROOT / 'delivery_audit.py'
MANIFEST = ROOT / 'execution-manifest.json'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = ROOT / 'native/proofs' / suffix / 'delivery'
        proof.mkdir(parents=True, exist_ok=True)
        commands = []
        for negative in (False, True):
            command = [sys.executable, '-B', str(SCRIPT), '--case', entry['case_id'],
                       '--selftest']
            if negative:
                command.append('--negative-fixture')
            result = subprocess.run(command, env=env, capture_output=True, text=True)
            path = proof / ('negative.log' if negative else 'positive.log')
            path.write_text((result.stdout + result.stderr).rstrip() + '\n')
            if (result.returncode == 0) == negative:
                raise RuntimeError('Independent delivery selftest had wrong exit')
            expected = 'Synthetic fixture cannot establish original Native delivery'
            if negative and expected not in path.read_text():
                raise RuntimeError('Synthetic rejection missing')
            commands.append((command, result.returncode, path))
        positive, negative = commands
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': CHECKS,
            'script': 'delivery_audit.py', 'script_sha256': sha(SCRIPT),
            'command': ' '.join(positive[0]), 'test_exit_code': positive[1],
            'test_log': str(positive[2].relative_to(ROOT)),
            'test_log_sha256': sha(positive[2]),
            'negative_command': ' '.join(negative[0]),
            'negative_exit_code': negative[1],
            'negative_expected_error': expected,
            'negative_log': str(negative[2].relative_to(ROOT)),
            'negative_log_sha256': sha(negative[2])}
    MANIFEST.write_text(json.dumps(manifest, indent=2).rstrip() + '\n')
    print('Two independent motorcycle delivery audit selftests bound')


if __name__ == '__main__':
    main()

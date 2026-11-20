"""Run positive synthetic and negative Native-provenance audits for each case."""
import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PREFIX = HERE.relative_to(REPO)
MANIFEST = HERE / 'execution-manifest.json'
SCRIPT = HERE / 'delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    result = subprocess.run(command, cwd=REPO, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'),
                            capture_output=True, text=True)
    log.write_text(result.stdout + result.stderr)
    return result.returncode


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        tokens = shlex.split(entry['compatibility']['replay_command'])
        attempt = tokens[tokens.index('--output') + 1]
        base = ['.venv-cpu/bin/python', str(PREFIX / SCRIPT.name), '--attempt', attempt,
                '--case', entry['case_id']]
        positive = HERE / 'cases' / suffix / 'delivery-positive.log'
        negative = HERE / 'cases' / suffix / 'delivery-negative.log'
        positive.parent.mkdir(parents=True, exist_ok=True)
        positive_command = base + ['--diagnostic-fixture']
        positive_code = run(positive_command, positive)
        negative_code = run(base, negative)
        expected_error = 'Native source provenance required'
        if positive_code != 0 or negative_code == 0 or expected_error not in negative.read_text():
            raise ValueError(f'Delivery audit failed for {suffix}: {positive_code}/{negative_code}; {positive.read_text()[:400]}')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-test', 'full-test'], 'checks': CHECKS,
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(positive_command), 'test_exit_code': positive_code,
            'test_log': str(positive.relative_to(HERE)), 'test_log_sha256': sha(positive),
            'negative_command': ' '.join(base), 'negative_exit_code': negative_code,
            'negative_expected_error': expected_error,
            'negative_log': str(negative.relative_to(HERE)), 'negative_log_sha256': sha(negative)}
        print(f'{suffix}: positive diagnostic and negative Native provenance checks passed')
    MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()

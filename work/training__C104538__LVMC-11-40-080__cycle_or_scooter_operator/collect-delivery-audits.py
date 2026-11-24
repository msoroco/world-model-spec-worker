"""Bind exact source-audit CPU positive and missing-rider negatives."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'native/delivery_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        case = entry['case_id']
        logs = {}
        for mode in ('selftest', 'negative-selftest'):
            command = [sys.executable, str(SCRIPT), '--case', case, '--' + mode]
            run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            log = HERE / ('delivery-' + suffix + '-' + mode + '.log')
            content = run.stdout if run.returncode == 0 else run.stderr
            log.write_text(content.rstrip() + '\n')
            if (mode == 'selftest' and run.returncode != 0 or
                    mode == 'negative-selftest' and
                    (run.returncode == 0 or 'Missing delivery source: rider_native_samples.jsonl' not in content)):
                raise RuntimeError(content[-2000:])
            logs[mode] = (run.returncode, log)
        pos, neg = logs['selftest'], logs['negative-selftest']
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': str(SCRIPT.relative_to(HERE)), 'script_sha256': sha(SCRIPT),
            'command': f'.venv-cpu/bin/python work/{HERE.name}/native/delivery_audit.py --case {case} --selftest',
            'test_exit_code': pos[0], 'test_log': str(pos[1].relative_to(HERE)),
            'test_log_sha256': sha(pos[1]),
            'negative_command': f'.venv-cpu/bin/python work/{HERE.name}/native/delivery_audit.py --case {case} --negative-selftest',
            'negative_exit_code': neg[0],
            'negative_expected_error': 'Missing delivery source: rider_native_samples.jsonl',
            'negative_log': str(neg[1].relative_to(HERE)),
            'negative_log_sha256': sha(neg[1]),
            'scope': 'synthetic CPU audit mechanics; original sign, rider posture and pedestrian-rule conduct pending'}
    write(manifest_path, manifest)
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()

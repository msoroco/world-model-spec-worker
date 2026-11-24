"""Run independent software delivery audits on all exact diagnostic attempts."""
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(path):
    path.write_text(path.read_text().rstrip() + '\n')


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = repo / '.runtime-work/c229439-saved-v2'
    script = folder / 'delivery_audit.py'

    def run(entry):
        case = entry['case_id']
        short = case.rsplit('__', 1)[-1]
        base = scratch / short
        positive = [sys.executable, str(script), '--attempt', str(base / 'attempt'), '--case', case]
        negative = [sys.executable, str(script), '--attempt', str(base / 'negative-attempt'),
                    '--case', case, '--negative']
        one = subprocess.run(positive, capture_output=True, text=True, env=os.environ.copy(), timeout=1200)
        if one.returncode:
            raise ValueError(short + ': delivery positive: ' + one.stderr[-700:])
        two = subprocess.run(negative, capture_output=True, text=True, env=os.environ.copy(), timeout=120)
        if two.returncode == 0 or 'Missing required source: device-source.json' not in two.stderr:
            raise ValueError(short + ': delivery negative: ' + two.stderr[-700:])
        return entry, short, positive, negative, one.stdout, two.stderr, two.returncode

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(run, manifest['cases']))
    for entry, short, positive, negative, good_log, bad_log, bad_code in outputs:
        case_dir = folder / 'cases' / short
        good = case_dir / 'delivery-positive.log'
        bad = case_dir / 'delivery-negative.log'
        good.write_text(good_log.rstrip() + '\n')
        bad.write_text(bad_log.rstrip() + '\n')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'scope': 'diagnostic software preflight; physical and legal acceptance pending original capture',
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(positive), 'test_exit_code': 0,
            'test_log': f'cases/{short}/delivery-positive.log', 'test_log_sha256': sha(good),
            'negative_command': ' '.join(negative), 'negative_exit_code': bad_code,
            'negative_expected_error': 'Missing required source: device-source.json',
            'negative_log': f'cases/{short}/delivery-negative.log', 'negative_log_sha256': sha(bad),
        }
        print(short + ': full decode and missing-device negative passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

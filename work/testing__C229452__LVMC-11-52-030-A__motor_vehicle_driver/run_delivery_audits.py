"""Bind exact independent positive/negative source and full-video audits."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c229452-saved-v1'
SCRIPT = ROOT / 'delivery_audit.py'
EXPECTED = 'Missing required source: original-red-curb-events.jsonl'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(entry):
    case = entry['case_id']
    short = case.rsplit('__', 1)[-1]
    base = SCRATCH / short
    good = [sys.executable, str(SCRIPT), '--attempt', str(base / 'attempt'), '--case', case]
    bad = [sys.executable, str(SCRIPT), '--attempt', str(base / 'negative-attempt'),
           '--case', case, '--negative']
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c229452-delivery-output'))
    positive = subprocess.run(good, cwd=REPO, env=env, capture_output=True, text=True, timeout=1200)
    negative = subprocess.run(bad, cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    if positive.returncode or negative.returncode == 0 or EXPECTED not in negative.stderr:
        raise ValueError(short + ': audit failed: ' + positive.stderr[-500:] + negative.stderr[-500:])
    return entry, short, good, bad, positive.stdout, negative.stderr, negative.returncode


def main():
    manifest = json.loads(MANIFEST.read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        outputs = list(pool.map(run, manifest['cases']))
    for entry, short, good, bad, good_log, bad_log, bad_code in outputs:
        folder = ROOT / 'cases' / short
        positive_log = folder / 'delivery-positive.log'
        negative_log = folder / 'delivery-negative.log'
        positive_log.write_text(good_log.rstrip() + '\n')
        negative_log.write_text(bad_log.rstrip() + '\n')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'scope': 'diagnostic software preflight; original physical and legal acceptance pending',
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': ' '.join(good), 'test_exit_code': 0,
            'test_log': str(positive_log.relative_to(ROOT)), 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(bad), 'negative_exit_code': bad_code,
            'negative_expected_error': EXPECTED,
            'negative_log': str(negative_log.relative_to(ROOT)),
            'negative_log_sha256': sha(negative_log)}
        print(short + ': independent diagnostic positive/negative passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

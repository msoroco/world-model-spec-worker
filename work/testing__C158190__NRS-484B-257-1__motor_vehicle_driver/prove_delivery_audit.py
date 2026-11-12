"""Bind independent positive/negative saved-source audit tests per exact case."""

import hashlib
import json
import os
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
ATTEMPTS = {
    'yield_nearest_view_through_approaches': '.runtime-work/c158190-yield_nearest_view_through_approaches-primary-compat-v4',
    'yield_nearest_view_through_entered': '.runtime-work/c158190-yield_nearest_view_through_entered-primary-compat-v4',
    'yield_nearest_view_clear': '.runtime-work/c158190-yield_nearest_view_clear-primary-compat-v4',
    'yield_nearest_view_no_slow': '.runtime-work/c158190-yield_nearest_view_no_slow-primary-compat-v4',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['PYTHONPATH'] = str(REPO / 'runtime/scenario_pipeline')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        folder = (ROOT / entry['construction']).parent
        base = ['.venv-cpu/bin/python', str((ROOT / 'delivery_audit.py').relative_to(REPO)),
                '--attempt', ATTEMPTS[suffix], '--case', entry['case_id']]
        positive = base + ['--diagnostic-fixture']
        negative = base
        pos = subprocess.run(positive, cwd=REPO, env=env, capture_output=True, text=True)
        neg = subprocess.run(negative, cwd=REPO, env=env, capture_output=True, text=True)
        pos_log, neg_log = folder / 'delivery-audit-positive.log', folder / 'delivery-audit-negative.log'
        pos_log.write_text(pos.stdout + pos.stderr)
        neg_log.write_text(neg.stdout + neg.stderr)
        expected = 'Independent original-camera pixel reviewer required'
        if pos.returncode or neg.returncode == 0 or expected not in neg_log.read_text():
            raise ValueError(f'{suffix}: independent audit tests failed; see {pos_log} and {neg_log}')
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['demo-test', 'full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(ROOT / 'delivery_audit.py'),
            'command': shlex.join(positive), 'test_exit_code': 0,
            'test_log': str(pos_log.relative_to(ROOT)), 'test_log_sha256': sha(pos_log),
            'negative_command': shlex.join(negative),
            'negative_exit_code': neg.returncode, 'negative_expected_error': expected,
            'negative_log': str(neg_log.relative_to(ROOT)),
            'negative_log_sha256': sha(neg_log),
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'case': suffix, 'positive': 0, 'negative': neg.returncode}), flush=True)


if __name__ == '__main__':
    main()

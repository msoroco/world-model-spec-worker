"""Run independent diagnostic and physical-source rejection audits."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
SCRIPT = FOLDER / 'delivery_acceptance.py'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, log):
    done = subprocess.run(args, cwd=REPO, capture_output=True, text=True)
    text = (done.stdout + done.stderr).rstrip() + '\n'
    log.write_text(text)
    return done.returncode


def main():
    path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        condition = case.rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / f'c111325-final-compat-{condition}-primary'
        positive = FOLDER / f'delivery-{condition}-positive.json'
        positive_log = FOLDER / f'delivery-{condition}-positive.log'
        negative = FOLDER / f'delivery-{condition}-negative.json'
        negative_log = FOLDER / f'delivery-{condition}-negative.log'
        base = [sys.executable, str(SCRIPT), '--attempt', str(source), '--case', case]
        passed = run(base + ['--diagnostic', '--output', str(positive)], positive_log)
        failed = run(base + ['--output', str(negative)], negative_log)
        expected = 'Missing delivery source: capture-seal.json'
        if passed != 0 or failed == 0 or expected not in negative_log.read_text():
            raise ValueError('Independent delivery audit did not show expected proof pair: ' + condition)
        report = json.loads(positive.read_text())
        if not report['diagnostic_fixture'] or report['physical_acceptance'] or report['frames'] != 600:
            raise ValueError('Diagnostic audit overstated acceptance')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': SCRIPT.name, 'script_sha256': sha(SCRIPT),
            'command': f'.venv-cpu/bin/python work/{FOLDER.name}/delivery_acceptance.py --attempt .runtime-work/c111325-final-compat-{condition}-primary --case {case} --diagnostic --output work/{FOLDER.name}/{positive.name}',
            'test_exit_code': passed, 'test_log': positive_log.name,
            'test_log_sha256': sha(positive_log),
            'negative_command': f'.venv-cpu/bin/python work/{FOLDER.name}/delivery_acceptance.py --attempt .runtime-work/c111325-final-compat-{condition}-primary --case {case} --output work/{FOLDER.name}/{negative.name}',
            'negative_exit_code': failed, 'negative_expected_error': expected,
            'negative_log': negative_log.name, 'negative_log_sha256': sha(negative_log),
            'proof_scope': 'Synthetic source join and synthetic-as-physical rejection only',
        }
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'delivery_proofs': len(manifest['cases']), 'manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()

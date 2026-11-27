"""Retain exact-case independent audit positive and rejection receipts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'
AUDIT = FOLDER / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    directory = FOLDER / 'delivery-proofs'
    directory.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        specs = {}
        for negative in (False, True):
            command = [str(ROOT / '.venv-cpu/bin/python'), '-B', str(AUDIT),
                       '--case', case, '--self-test']
            if negative:
                command.append('--negative')
            label = 'negative' if negative else 'positive'
            path = directory / f'{suffix}-{label}.log'
            with path.open('w') as log:
                status = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
            if (status.returncode == 0) == negative:
                raise ValueError(f'Audit {suffix} {label} returned unexpected status')
            if negative and 'Missing original source: exact original Native result' not in path.read_text():
                raise ValueError('Missing declared negative rejection')
            specs[label] = {'command': ' '.join(command), 'exit_code': status.returncode,
                            'log': str(path.relative_to(FOLDER)), 'log_sha256': sha(path)}
        positive, negative = specs['positive'], specs['negative']
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': 'delivery_audit.py', 'script_sha256': sha(AUDIT),
            'command': positive['command'], 'test_exit_code': 0,
            'test_log': positive['log'], 'test_log_sha256': positive['log_sha256'],
            'negative_command': negative['command'], 'negative_exit_code': negative['exit_code'],
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': negative['log'], 'negative_log_sha256': negative['log_sha256'],
            'scope': 'CPU source predicates; original Native review pending'}
        print(suffix, 'positive and negative audit tests passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()

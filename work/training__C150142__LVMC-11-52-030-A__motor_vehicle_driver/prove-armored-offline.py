"""Run pinned offline checks for all four exact armored draft candidates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
PYTHON = sys.executable


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records = []
    for sign in ('unsigned', 'signed'):
        for activity in ('business', 'no_business'):
            slug = 'armored_car_' + sign + '_' + activity
            manifest = ROOT / ('execution-manifest-diagnostic-' + slug + '-draft.json')
            for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
                output = REPO / '.runtime-work' / ('c150142-' + slug + '-' +
                                                   candidate + '-offline-v2')
                if output.exists():
                    raise ValueError('Retain prior offline attempt: ' + str(output))
                command = [PYTHON, str(REPO / 'runtime.py'), 'offline',
                           '--manifest', str(manifest),
                           '--case', ROOT.name + '__' + slug,
                           '--candidate', candidate, '--output', str(output),
                           '--python', PYTHON]
                process = subprocess.run(command, cwd=REPO, text=True,
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, timeout=300)
                log = output / 'offline.log'
                records.append({'case': slug, 'candidate': candidate,
                                'returncode': process.returncode,
                                'manifest_sha256': sha(manifest),
                                'offline_log_sha256': sha(log) if log.exists() else None,
                                'runtime_response': process.stdout[-1800:]})
    summary = {'kind': 'armored_visual_proxy_offline_diagnostic',
               'original_native_observed': False,
               'legal_armored_identity_verified': False,
               'all_passed': all(row['returncode'] == 0 for row in records),
               'candidates': records}
    target = ROOT / 'update043-armored-offline-matrix.json'
    target.write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'all_passed': summary['all_passed'],
                      'count': len(records), 'receipt': str(target.relative_to(REPO))}))
    return 0 if summary['all_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

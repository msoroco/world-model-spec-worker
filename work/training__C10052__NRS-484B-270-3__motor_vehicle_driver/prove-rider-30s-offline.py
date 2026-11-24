"""Run pinned offline checks on the four exact 30 s rider drafts."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = HERE / 'rider-30s-primary'
MANIFEST = PACKAGE / 'draft-manifest.json'
CASE = HERE.name + '__rider_bicycle_clear'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    receipts = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c10052-rider-30s-offline-') as temp:
        for candidate in CANDIDATES:
            command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', CASE,
                       '--candidate', candidate, '--output', str(Path(temp) / candidate),
                       '--python', sys.executable]
            process = subprocess.run(command, cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=300)
            log = PACKAGE / (candidate + '-offline.log')
            log.write_text(process.stdout)
            if process.returncode:
                raise AssertionError(candidate + ' offline failed: ' + process.stdout)
            construction = PACKAGE / ('construction.json' if candidate == 'primary'
                                      else candidate + '/construction.json')
            receipts.append({'candidate_id': candidate, 'command': command,
                             'exit_code': process.returncode,
                             'construction_sha256': sha(construction),
                             'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log)})
    summary = {'format': 'c10052-rider-30s-offline-matrix-v1',
               'case_id': CASE, 'selected': False, 'accepted': False,
               'manifest_sha256': sha(MANIFEST), 'duration_s': 30,
               'rate_hz': 20, 'expected_frames': 600, 'receipts': receipts}
    output = PACKAGE / 'rider-offline-matrix.json'
    output.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'summary_sha256': sha(output),
                      'candidate_count': len(receipts), 'passed': True}))


if __name__ == '__main__':
    main()

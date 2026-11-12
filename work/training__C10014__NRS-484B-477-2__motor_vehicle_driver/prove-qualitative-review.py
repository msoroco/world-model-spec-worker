"""Retain the exact CPU reviewer-contract tests without claiming a legal result."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PYTHON = REPO / '.venv-cpu/bin/python'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    command = [str(PYTHON), '-m', 'unittest', 'discover', '-s',
               str(HERE / 'tests'), '-p', 'test_qualitative_review.py', '-v']
    result = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
    log = HERE / 'qualitative-review-cpu-tests.log'
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError('Qualitative reviewer CPU proof failed')
    proof = {'format': 'c10014-qualitative-review-cpu-proof-v1',
             'script': 'qualitative_review.py',
             'script_sha256': sha(HERE / 'qualitative_review.py'),
             'law_input_sha256': sha(REPO / 'inputs' / HERE.name /
                                     'assignment.json'),
             'command': ' '.join(command), 'exit_code': result.returncode,
             'log': log.name, 'log_sha256': sha(log),
             'source_shaped_tests': 3, 'original_source_review_completed': False,
             'legal_verdict_claimed': False}
    path = HERE / 'qualitative-review-cpu-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'tests': 3, 'proof_sha256': sha(path),
                      'original_source_review_completed': False}))


if __name__ == '__main__':
    main()

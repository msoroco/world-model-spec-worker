"""Bind tested saved-only post-capture commands for every exact case."""
import hashlib
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        saved = entry['saved_processing']
        receipt = json.loads((PACKAGE / saved['receipt']).read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != case
                or receipt.get('recorded_only') is not True or not receipt.get('originals_preserved')
                or receipt.get('missing_evidence') is not False):
            raise ValueError('Saved-only fixture proof incomplete: ' + case)
        command = (' '.join([str(Path(sys.executable).resolve()), str(ROOT / 'runtime.py'),
                             'process-saved', '--manifest', str(MANIFEST),
                             '--case', case, '--attempt', '"$SAVED_ATTEMPT"',
                             '--output', '"$PROCESSED_OUT"', '--library', str(ROOT / 'runtime/library'),
                             '--validator', str(ROOT / '.runtime-work/c229597-library-current/.lake/build/bin/adapterCheck')]))
        entry['post_capture'] = {
            'recorded_only': True, 'command': command,
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': saved['log'], 'test_log_sha256': sha(PACKAGE / saved['log']),
            'fixture_receipt': saved['receipt'], 'fixture_receipt_sha256': saved['sha256'],
            'scope': 'saved synthetic CPU fixture; local Native capture remains pending'}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

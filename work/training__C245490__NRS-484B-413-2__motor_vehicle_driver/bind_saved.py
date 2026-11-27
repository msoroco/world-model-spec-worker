"""Retain exact recorded-only diagnostic receipts for all selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    folder = HERE / 'saved'
    folder.mkdir(exist_ok=True)
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        version = REPO / '.runtime-work' / ('c245490_saved_v2_' + suffix) / 'v0001'
        receipt = json.loads((version / 'processing.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
                or receipt.get('originals_preserved') is not True
                or receipt.get('analysis_revision', {}).get('construction_sha256') != entry['construction_sha256']):
            raise ValueError('Recorded-only proof missing or stale: ' + suffix)
        log = folder / (suffix + '-analysis.log')
        log.write_text((version / 'analysis.log').read_text().rstrip() + '\n')
        copy = folder / (suffix + '-processing.json')
        copy.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python -B runtime.py process-saved --manifest '
                + 'work/' + HERE.name + '/execution-manifest.json --case ' + entry['case_id']
                + ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json # ' + entry['case_id'],
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': str(log.relative_to(HERE)), 'test_log_sha256': sha(log),
            'processing_receipt': str(copy.relative_to(HERE)), 'processing_receipt_sha256': sha(copy),
            'diagnostic_scope': 'Synthetic saved-only test; original Native processing pending'}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()

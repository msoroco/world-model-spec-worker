"""Bind passed recorded-only and physical diagnostic CPU proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parents[1]
ROOT = HERE.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(source, target):
    rows = [line.rstrip() for line in source.read_text().splitlines()]
    while rows and not rows[-1]:
        rows.pop()
    target.write_text('\n'.join(rows) + '\n' if rows else '')


def main():
    path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        saved = ROOT / '.runtime-work' / f'c110875-saved-probe_{suffix[-2:]}-primary-1' / 'v0001'
        receipt = json.loads((saved / 'processing.json').read_text())
        if receipt['case_id'] != case or receipt['missing_evidence'] or not receipt['passed']:
            raise ValueError('Recorded-only proof failed: ' + case)
        proof = FOLDER / 'proofs' / suffix
        source_log = ROOT / '.runtime-work' / 'c110875-native-tmp' / f'saved-{suffix}-primary-1.log'
        clean(source_log, proof / 'saved.log')
        physical = proof / 'physical-preparation.json'
        if not physical.is_file():
            raise FileNotFoundError(physical)
        entry['physical_preparation'] = {'receipt': f'proofs/{suffix}/physical-preparation.json',
            'sha256': sha(physical)}
        entry['post_capture'] = {'recorded_only': True,
            'command': f'runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json',
            'test_log': f'proofs/{suffix}/saved.log',
            'test_log_sha256': sha(proof / 'saved.log'), 'test_exit_code': 0}
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'recorded_only_cases': len(manifest['cases'])}))


if __name__ == '__main__':
    main()

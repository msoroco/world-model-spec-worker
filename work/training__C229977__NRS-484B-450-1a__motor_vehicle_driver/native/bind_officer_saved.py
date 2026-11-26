"""Bind exact recorded-only officer-candidate saved receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_log(source, target):
    raw = source.read_text()
    if any(line.rstrip() != line for line in raw.splitlines()):
        raise ValueError('Trailing whitespace in saved log')
    target.write_text(raw.rstrip() + '\n')


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    folder = HERE / 'saved'
    folder.mkdir(exist_ok=True)
    for state in ('absent', 'present'):
        name = f'officer_direction_{state}'
        case_id = f'{HERE.name}__{name}'
        entry = entries[case_id]
        base = REPO / '.runtime-work' / f'c229977-officer-saved-{name}'
        proofs = {}
        for kind in ('positive', 'negative'):
            result = json.loads((Path(f'{base}-{kind}' + ('-v2' if kind == 'positive' else '')) / 'v0001/processing.json').read_text())
            if not result['passed'] or not result['recorded_only'] or not result['originals_preserved']:
                raise ValueError(f'Saved {name}/{kind} did not pass')
            if bool(result['missing_evidence']) != (kind == 'negative'):
                raise ValueError(f'Saved {name}/{kind} source state differs')
            receipt = folder / f'{name}-{kind}.json'
            receipt.write_text(json.dumps(result, indent=2) + '\n')
            log = folder / f'{name}-{kind}.log'
            log.write_text(log.read_text().rstrip() + '\n')
            proofs[kind] = (receipt, log)
        command = (f'.venv-cpu/bin/python -B runtime.py process-saved --manifest '
                   f'work/{HERE.name}/execution-manifest.json --case {case_id} '
                   '--attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library '
                   '--validator $DECODER')
        positive_receipt, positive_log = proofs['positive']
        negative_receipt, negative_log = proofs['negative']
        entry['post_capture'] = {
            'recorded_only': True, 'command': command, 'feedback_command': command,
            'test_exit_code': 0, 'test_log': str(positive_log.relative_to(HERE)),
            'test_log_sha256': sha(positive_log),
            'processing_receipt': str(positive_receipt.relative_to(HERE)),
            'processing_receipt_sha256': sha(positive_receipt),
            'missing_source_test_exit_code': 0,
            'missing_source_log': str(negative_log.relative_to(HERE)),
            'missing_source_log_sha256': sha(negative_log),
            'missing_source_receipt': str(negative_receipt.relative_to(HERE)),
            'missing_source_receipt_sha256': sha(negative_receipt)}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    main()

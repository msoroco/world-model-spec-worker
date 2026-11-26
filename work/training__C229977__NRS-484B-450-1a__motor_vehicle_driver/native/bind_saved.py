"""Bind completed recorded-only saved processing proofs."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = FOLDER / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    target = FOLDER / 'saved'
    target.mkdir(exist_ok=True)
    for index, entry in enumerate(manifest['cases'], 1):
        source = REPO / '.runtime-work' / f'c229977-saved-v9-probe{index}-positive'
        result = json.loads((source / 'v0001/processing.json').read_text())
        if not result['passed'] or not result['recorded_only'] or not result['originals_preserved']:
            raise ValueError('Saved processing did not pass')
        name = f'probe_{index}'
        log = target / (name + '-processing.log')
        raw = (REPO / '.runtime-work' / f'c229977-saved-v9-probe{index}-positive.log').read_text()
        if any(line.rstrip() != line for line in raw.splitlines()):
            raise ValueError('Saved log has trailing whitespace')
        log.write_text(raw.rstrip() + '\n')
        receipt = target / (name + '-processing.json')
        receipt.write_text(json.dumps(result, indent=2) + '\n')
        negative_source = REPO / '.runtime-work' / f'c229977-saved-v9-probe{index}-negative'
        negative_result = json.loads((negative_source / 'v0001/processing.json').read_text())
        if not negative_result['passed'] or not negative_result['missing_evidence'] or not negative_result['originals_preserved']:
            raise ValueError('Missing-source saved path did not preserve originals')
        negative_log = target / (name + '-missing-source.log')
        negative_raw = (REPO / '.runtime-work' / f'c229977-saved-v9-probe{index}-negative.log').read_text()
        if any(line.rstrip() != line for line in negative_raw.splitlines()):
            raise ValueError('Missing-source saved log has trailing whitespace')
        negative_log.write_text(negative_raw.rstrip() + '\n')
        negative_receipt = target / (name + '-missing-source.json')
        negative_receipt.write_text(json.dumps(negative_result, indent=2) + '\n')
        command = (f'.venv-cpu/bin/python -B runtime.py process-saved --manifest '
                   f'work/{FOLDER.name}/execution-manifest.json --case {entry["case_id"]} '
                   '--attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library '
                   '--validator $DECODER')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': command,
            'feedback_command': command,
            'test_exit_code': 0,
            'test_log': str(log.relative_to(FOLDER)),
            'test_log_sha256': sha(log),
            'processing_receipt': str(receipt.relative_to(FOLDER)),
            'processing_receipt_sha256': sha(receipt),
            'missing_source_test_exit_code': 0,
            'missing_source_log': str(negative_log.relative_to(FOLDER)),
            'missing_source_log_sha256': sha(negative_log),
            'missing_source_receipt': str(negative_receipt.relative_to(FOLDER)),
            'missing_source_receipt_sha256': sha(negative_receipt)}
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(sha(path))


if __name__ == '__main__':
    bind()

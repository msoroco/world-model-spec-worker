"""Bind recorded-only device-candidate saved proofs to exact selected cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def bind():
    path = HERE / 'device-execution-manifest.json'
    manifest = json.loads(path.read_text())
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    for state in ('absent', 'present'):
        suffix = 'official_device_' + state
        case_id = HERE.name + '__' + suffix
        entry = entries[case_id]
        proofs = {}
        for kind in ('positive', 'negative'):
            base = REPO / '.runtime-work' / f'c229977-device-{state}-saved-{kind}-v2' / 'v0001'
            receipt = json.loads((base / 'processing.json').read_text())
            if (not receipt['passed'] or not receipt['recorded_only'] or
                    not receipt['originals_preserved'] or
                    bool(receipt['missing_evidence']) != (kind == 'negative')):
                raise ValueError('Recorded-only device source proof differs: ' + suffix + '/' + kind)
            output = HERE / 'saved' / f'{suffix}-{kind}.json'
            dump(output, receipt)
            log = HERE / 'saved' / f'{suffix}-{kind}.log'
            log.write_text((base / 'analysis.log').read_text().rstrip() + '\n')
            proofs[kind] = (output, log)
        command = (f'.venv-cpu/bin/python -B runtime.py process-saved --manifest '
                   f'work/{HERE.name}/execution-manifest.json --case {case_id} '
                   '--attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library '
                   '--validator $DECODER')
        positive_receipt, positive_log = proofs['positive']
        negative_receipt, negative_log = proofs['negative']
        entry['post_capture'] = {
            'recorded_only': True, 'command': command, 'feedback_command': command,
            'test_exit_code': 0,
            'test_log': str(positive_log.relative_to(HERE)),
            'test_log_sha256': sha(positive_log),
            'processing_receipt': str(positive_receipt.relative_to(HERE)),
            'processing_receipt_sha256': sha(positive_receipt),
            'missing_source_test_exit_code': 0,
            'missing_source_log': str(negative_log.relative_to(HERE)),
            'missing_source_log_sha256': sha(negative_log),
            'missing_source_receipt': str(negative_receipt.relative_to(HERE)),
            'missing_source_receipt_sha256': sha(negative_receipt)}
    dump(path, manifest)
    return sha(path)


if __name__ == '__main__':
    print(bind())

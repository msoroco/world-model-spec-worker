"""Bind verified recorded-only CPU receipts to seven exact delivery cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
MANIFEST = PACKAGE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[1]
        if suffix == 'probe_03':
            continue
        prefix = HERE / 'saved' / suffix
        positive = Path(str(prefix) + '-positive-processing.json')
        negative = Path(str(prefix) + '-negative-processing.json')
        feedback = Path(str(prefix) + '-negative-feedback.json')
        for path in (positive, negative, feedback):
            if not path.is_file():
                raise ValueError('Missing recorded-only CPU proof: ' + str(path))
        good = json.loads(positive.read_text())
        bad = json.loads(negative.read_text())
        rejected = json.loads(feedback.read_text())
        if good.get('case_id') != entry['case_id'] or not good.get('passed') or \
                not good.get('recorded_only') or \
                good.get('native_revision', {}).get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('Positive saved receipt differs from exact case: ' + suffix)
        if bad.get('case_id') != entry['case_id'] or not bad.get('recorded_only') or \
                rejected.get('classification') != 'incomplete_or_unavailable_law_evidence' or \
                'Missing required source: school_zone_context.json' not in rejected.get('error', ''):
            raise ValueError('Missing-context saved rejection differs: ' + suffix)
        command = ('.venv-cpu/bin/python -B runtime.py process-saved --manifest '
                   f'work/{PACKAGE.name}/execution-manifest.json --case {entry["case_id"]} '
                   '--attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library '
                   '--validator $DECODER')
        entry['post_capture'] = {
            'command': command, 'feedback_command': command, 'recorded_only': True,
            'test_exit_code': 0,
            'test_log': str(positive.relative_to(PACKAGE)),
            'test_log_sha256': sha(positive),
            'processing_receipt': str(positive.relative_to(PACKAGE)),
            'processing_receipt_sha256': sha(positive),
            'negative_processing_receipt': str(negative.relative_to(PACKAGE)),
            'negative_processing_receipt_sha256': sha(negative),
            'negative_feedback': str(feedback.relative_to(PACKAGE)),
            'negative_feedback_sha256': sha(feedback),
        }
        print(suffix, sha(positive), sha(feedback))
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()

"""Record exact saved-only diagnostic processing and incomplete-source feedback."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for index, entry in enumerate(manifest['cases'], 1):
        log = HERE / f'saved-{index}-primary.log'
        result = json.loads(log.read_text())
        if (result.get('case_id') != entry['case_id'] or result.get('missing_evidence') is not False
                or result.get('originals_preserved') is not True
                or result.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Saved-only positive proof differs: ' + entry['case_id'])
        entry['post_capture'] = {
            'recorded_only': True,
            'command': ('runtime.py process-saved --manifest work/' + BASE +
                        '/execution-manifest.json --case ' + entry['case_id'] +
                        ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER'),
            'feedback_command': ('cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']),
            'test_log': log.name, 'test_log_sha256': sha(log), 'test_exit_code': 0}
    negative = json.loads((HERE / 'saved-1-negative.log').read_text())
    feedback_source = HERE.parents[1] / '.runtime-work/c109166-saved-r3-negative/v0001/feedback.json'
    feedback = json.loads(feedback_source.read_text())
    if (negative.get('missing_evidence') is not True or
            feedback.get('classification') != 'incomplete_or_unavailable_law_evidence' or
            'Missing required source: device-original.jsonl' not in feedback.get('error', '')):
        raise ValueError('Saved-only missing-source feedback not demonstrated')
    feedback_target = HERE / 'cases/controlled_1/saved-negative-feedback.json'
    shutil.copyfile(feedback_source, feedback_target)
    write(HERE / 'saved-only-proof.json', {
        'format': 'c109166-saved-only-proof-v1', 'case_count': 2,
        'positive_logs': {str(i): sha(HERE / f'saved-{i}-primary.log') for i in (1, 2)},
        'negative_log_sha256': sha(HERE / 'saved-1-negative.log'),
        'negative_feedback': str(feedback_target.relative_to(HERE)),
        'negative_feedback_sha256': sha(feedback_target),
        'native_executed': False, 'original_authority_reviewed': False,
        'physical_acceptance_claimed': False})
    write(manifest_path, manifest)
    print(json.dumps({'saved_cases': 2, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()

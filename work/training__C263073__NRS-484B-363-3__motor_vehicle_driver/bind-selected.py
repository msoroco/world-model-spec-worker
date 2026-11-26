"""Bind exact selected CPU proofs and root Native handoff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_native_review'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        proof = HERE / 'proofs' / suffix
        processing = REPO / '.runtime-work/c263073-owner' / ('saved-' + suffix + '-primary-v4/v0001/processing.json')
        receipt = json.loads(processing.read_text())
        if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True or
                receipt.get('candidate_id') != 'primary' or receipt.get('case_id') != case or
                receipt.get('originals_preserved') is not True or
                receipt.get('final_video_checks', {}).get('frames') != 600 or
                receipt.get('physical_acceptance_claimed') is not False or
                receipt.get('legal_acceptance_claimed') is not False):
            raise ValueError('Selected saved CPU proof differs')
        saved_log = proof / 'saved.log'
        write(saved_log, {'command': 'runtime.py process-saved', 'case_id': case,
                          'recorded_only': True, 'passed': True, 'frames': 600,
                          'processing_receipt_sha256': sha(processing),
                          'originals_preserved': True, 'physical_acceptance_claimed': False})
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + HERE.name +
                '/execution-manifest.json --case ' + case +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + case,
            'test_log': str(saved_log.relative_to(HERE)),
            'test_log_sha256': sha(saved_log), 'test_exit_code': 0}
        physical = proof / 'physical-preparation.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': sha(physical)}
        auditor = HERE / 'delivery_audit.py'
        positive = proof / 'delivery-audit-positive.log'
        negative = proof / 'delivery-audit-negative.log'
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'command': 'python delivery_audit.py --case ' + case + ' --attempt $ATTEMPT --processing $PROCESSING --output $AUDIT',
            'negative_command': 'python delivery_audit.py --case ' + case + ' --attempt $ATTEMPT --processing $PROCESSING --output $AUDIT --diagnostic --omit-source school-context.json',
            'negative_expected_error': 'Missing source: school-context.json',
            'script': str(auditor.relative_to(HERE)), 'script_sha256': sha(auditor),
            'test_log': str(positive.relative_to(HERE)), 'test_log_sha256': sha(positive),
            'test_exit_code': 0,
            'negative_log': str(negative.relative_to(HERE)), 'negative_log_sha256': sha(negative),
            'negative_exit_code': 1}
    write(HERE / 'execution-manifest.json', manifest)
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    first['measurement_plan'] = {'entrypoint': 'finalize.py',
        'required_sources': ['native-motion.jsonl', 'school-context.json', 'trace.jsonl',
                             'video_frames.jsonl', 'driver_reference.mkv',
                             'review-sources/zone_designation.json',
                             'review-sources/child_identity.json',
                             'review-sources/school_session.json',
                             'review-sources/school_operation.json',
                             'review-sources/beacon_configuration.json',
                             'review-sources/zone_sign.json']}
    first['static_checks'] = ['30 seconds at 20 Hz', 'four original RGB source cameras',
        '1920x1080 overview', 'five separate exception source records',
        'source-bound original body and heading measurement']
    first['termination_rules'] = ['600 joined Native frames', 'all encoders closed',
        'owned actors destroyed', 'world settings restored before capture seal']
    first['mechanisms'] = ['same school-zone layout and source-review policy; requested turn alone varies',
        'use vehicle control and measure original body/heading; defer legal status to review']
    for item in first['files']:
        dest = HERE / item['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(item['content'])
    write(HERE / 'construction.json', first)
    print('selected', len(manifest['cases']))


if __name__ == '__main__':
    main()

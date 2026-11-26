"""Independent source audit for C111334 saved attempts.

Diagnostic fixtures exercise the checks without asserting physical acceptance.
"""

import argparse
import hashlib
import json
from pathlib import Path

from selected_finalize import source_join_measurement


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, case_id, diagnostic=False, owner_receipt=None,
          processing_receipt=None):
    attempt = Path(attempt)
    config_path = attempt / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing delivery source: config.json')
    config = json.loads(config_path.read_text())
    if config.get('case_id') != case_id or config.get('selected_case_id') != case_id:
        raise ValueError('Wrong exact delivery case')
    measured = source_join_measurement(attempt)
    if measured['case_id'] != case_id or not measured['green_arrow_alone_facing_throughout']:
        raise ValueError('Facing arrow context or source identity incomplete')
    if diagnostic:
        if measured['source_kind'] != 'synthetic_cpu_fixture':
            raise ValueError('Diagnostic mode requires synthetic sources')
    else:
        if measured['source_kind'] != 'original_native' or not measured['original_native_observed']:
            raise ValueError('Original Native delivery source required')
        for name in ('capture-seal.json', 'native-capture-report.json'):
            if not (attempt / name).is_file():
                raise ValueError('Missing delivery source: ' + name)
        for path, label in ((owner_receipt, 'owner release'),
                            (processing_receipt, 'saved processing')):
            if not path or not Path(path).is_file():
                raise ValueError('Missing ' + label + ' receipt')
    mapping_sha = sha(attempt / 'video_frames.jsonl')
    decoded = {}
    for index, name in enumerate(VIEWS):
        decode_path = attempt / ('source-' + str(index) + '.json')
        if not decode_path.is_file():
            raise ValueError('Missing source decode: ' + name)
        decode = json.loads(decode_path.read_text())
        if (decode.get('format') != 'source-decode' or
                decode.get('passed') is not True or decode.get('frames') != 600 or
                decode.get('video_sha256') != sha(attempt / (name + '.mkv')) or
                decode.get('mapping_sha256') != mapping_sha):
            raise ValueError('Source decode binding differs: ' + name)
        decoded[name] = sha(decode_path)
    primary = attempt / 'event_review.webm'
    primary_decode = attempt / 'final-decode.json'
    if not primary.is_file() or not primary_decode.is_file():
        raise ValueError('Missing composed primary decode')
    final = json.loads(primary_decode.read_text())
    if (final.get('format') != 'source-decode' or
            final.get('passed') is not True or final.get('frames') != 600 or
            final.get('video_sha256') != sha(primary)):
        raise ValueError('Composed primary decode binding differs')
    source_names = ('config.json', 'c111334-native-samples.jsonl',
                    'video_frames.jsonl', 'device-review.json') + tuple(
                        name + '.mkv' for name in VIEWS)
    return {
        'format': 'c111334-independent-delivery-audit-v1',
        'case_id': case_id,
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'source_hashes': {name: sha(attempt / name) for name in source_names},
        'source_decode_receipts': decoded,
        'primary_decode_receipt_sha256': sha(primary_decode),
        'first_highway_entry_frame': measured['first_highway_entry_frame'],
        'other_device_permission_at_first_entry':
            measured['other_device_permission_at_first_entry'],
        'frames': 600,
        'diagnostic_fixture': diagnostic,
        'original_native_observed': measured['original_native_observed'],
        'actual_pixels_reviewed': False,
        'physical_acceptance': False,
        'legal_verdict': None,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--owner-receipt')
    parser.add_argument('--processing-receipt')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, args.diagnostic,
                   args.owner_receipt, args.processing_receipt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture': args.diagnostic,
                      'source_join_passed': True}, sort_keys=True))

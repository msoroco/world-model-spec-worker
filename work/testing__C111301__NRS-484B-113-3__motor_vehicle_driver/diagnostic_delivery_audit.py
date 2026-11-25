"""Independent saved-source audit of diagnostic software evidence only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from backing_measurements import compare
from media_decode import audit_media
from saved_backing import ASSIGNMENT, process


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_case(attempt, processing, suffix):
    attempt, processing = Path(attempt).resolve(), Path(processing).resolve()
    case = ASSIGNMENT + '__' + suffix
    marker = json.loads((attempt / 'diagnostic-fixture.json').read_text())
    if marker != {'format': 'worker-diagnostic-fixture', 'diagnostic_fixture': True}:
        raise ValueError('explicit synthetic fixture declaration required')
    measured = process(attempt, case, allow_diagnostic=True)
    if measured['provenance_kind'] != 'synthetic_fixture':
        raise ValueError('diagnostic source was not labeled synthetic')
    receipt = json.loads(processing.read_text())
    if (receipt.get('case_id') != case or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('missing_evidence') is not False):
        raise ValueError('recorded-only proof is incomplete')
    for relative, checksum in receipt['original_source_hashes'].items():
        if sha(attempt / relative) != checksum:
            raise ValueError('saved original source differs: ' + relative)
    if sha(receipt['result']) != receipt['result_sha256']:
        raise ValueError('saved result differs from recorded-only receipt')
    video = audit_media(attempt, json.loads((attempt / 'acquisition.json').read_text()))
    if not video['actual_pixels_decoded'] or video['frame_count'] != 900:
        raise ValueError('complete independent four-camera decode required')
    return {'format': 'worker-diagnostic-delivery-audit', 'case_id': case,
            'diagnostic_fixture': True, 'provenance_kind': 'synthetic_fixture',
            'acquisition_sha256': measured['acquisition_sha256'],
            'processing_sha256': sha(processing),
            'saved_result_sha256': receipt['result_sha256'],
            'source_hashes_rechecked': len(receipt['original_source_hashes']),
            'camera_decode': video, 'frame_count': 900,
            'response_witness': measured['response_witness'],
            'physical_completion': False, 'legal_judgment': 'unresolved'}, measured


def main():
    parser = argparse.ArgumentParser()
    for suffix in ('yield', 'continue'):
        parser.add_argument('--' + suffix + '-attempt', required=True)
        parser.add_argument('--' + suffix + '-processing', required=True)
        parser.add_argument('--' + suffix + '-output', required=True)
    parser.add_argument('--comparison-output', required=True)
    args = parser.parse_args()
    receipts = {}
    measured = {}
    for short, suffix in (('yield', 'pedestrian_yield'),
                          ('continue', 'pedestrian_continue')):
        receipts[short], measured[short] = audit_case(
            getattr(args, short + '_attempt'),
            getattr(args, short + '_processing'), suffix)
        Path(getattr(args, short + '_output')).write_text(
            json.dumps(receipts[short], indent=2) + '\n')
    left, right = measured['yield'], measured['continue']
    if left['map_sha256'] != right['map_sha256']:
        raise ValueError('comparison map source changed')
    if [r['time_s'] for r in left['measurement']['frames']] != [
            r['time_s'] for r in right['measurement']['frames']]:
        raise ValueError('comparison time window changed')
    difference = compare(left['measurement'], right['measurement'])
    output = {'format': 'worker-diagnostic-comparison-audit',
              'comparison_id': 'pedestrian_yield_response',
              'diagnostic_fixture': True,
              'case_ids': [left['case_id'], right['case_id']],
              'fixed_original_map_sha256': left['map_sha256'],
              'source_ids': difference['sources'],
              'changed_observables': difference['changed_observables'],
              'fixed_observables': difference['fixed_observables'] + ['time_s', 'map_sha256'],
              'delivery_audit_sha256': [sha(getattr(args, s + '_output'))
                                        for s in ('yield', 'continue')],
              'physical_completion': False, 'legal_judgment': 'unresolved'}
    Path(args.comparison_output).write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'case_audits': list(receipts), 'comparison_id': output['comparison_id'],
                      'physical_completion': False}))


if __name__ == '__main__':
    main()

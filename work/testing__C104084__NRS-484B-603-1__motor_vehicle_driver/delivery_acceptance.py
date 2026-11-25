"""Independent audit of original Native saved media and physical review.

A CPU fixture exercises this path only with the explicit diagnostic flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest_media import audit_media


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_review(case: str, manifest_sha: str, source_proof: dict,
                    receipt: dict, *, diagnostic_test: bool = False) -> dict:
    if not isinstance(receipt, dict) or receipt.get('case_id') != case:
        raise ValueError('original Native review case differs')
    kind = 'diagnostic_fixture_review' if diagnostic_test else 'original_native_review'
    if receipt.get('provenance_kind') != kind:
        raise ValueError('original Native physical review required')
    if receipt.get('diagnostic_fixture') is not diagnostic_test:
        raise ValueError('review diagnostic provenance differs')
    expected = {
        'crest_manifest_sha256': manifest_sha,
        'motion_sha256': source_proof['source_sha256']['motion'],
        'frame_map_sha256': source_proof['source_sha256']['frame_map'],
        'camera_rgb24_sha256': {name: row['decoded_rgb24_sha256']
                                for name, row in source_proof['camera_decodes'].items()},
        'frame_count': 900, 'rate_hz': 20,
    }
    if receipt.get('source_binding') != expected:
        raise ValueError('original Native review source/time/pixels binding differs')
    observer = receipt.get('reviewer')
    if not isinstance(observer, str) or not observer.strip():
        raise ValueError('independent physical reviewer required')
    crossing = source_proof['crest_crossing']
    passage = receipt.get('physical_completion')
    if not isinstance(passage, dict) or passage.get('status') not in ('met', 'not_met'):
        raise ValueError('reviewed physical completion outcome missing')
    if (passage.get('crossing_frame_id') != crossing.get('crossing_frame_id') or
            passage.get('crossing_time_s') != crossing.get('crossing_time_s')):
        raise ValueError('reviewed crest crossing time differs from original motion')
    if not diagnostic_test and passage['status'] != 'met':
        raise ValueError('reviewed original Native physical completion not met')
    visibility = receipt.get('visibility_review')
    if not isinstance(visibility, dict) or visibility.get('status') not in ('visible', 'not_visible'):
        raise ValueError('original Native visibility review missing')
    for key in ('ego_body', 'opposing_body', 'crest_approach'):
        row = visibility.get(key)
        if not isinstance(row, dict) or row.get('camera') not in source_proof['camera_decodes']:
            raise ValueError('visibility subject or original camera missing: ' + key)
        frame = row.get('video_frame')
        if type(frame) is not int or not 0 <= frame < 900 or type(row.get('visible')) is not bool:
            raise ValueError('visibility frame or observation invalid: ' + key)
        if not isinstance(row.get('observation'), str) or not row['observation'].strip():
            raise ValueError('independent visibility observation missing: ' + key)
        if not diagnostic_test and row['visible'] is not True:
            raise ValueError('original Native subject not visible: ' + key)
    if not isinstance(visibility.get('sight_line_observation'), str) or not visibility['sight_line_observation'].strip():
        raise ValueError('reviewed original sight line observation missing')
    if not diagnostic_test and visibility['status'] != 'visible':
        raise ValueError('original Native visibility unresolved')
    return {'physical_completion': passage['status'],
            'visibility': visibility['status'], 'reviewer': observer}


def accept(case: str, attempt: Path, processing: Path, review: Path,
           *, diagnostic_test: bool = False, omit_limit: bool = False) -> dict:
    acquisition = json.loads((attempt / 'acquisition-provenance.json').read_text(encoding='utf-8'))
    seal = json.loads((attempt / 'capture-seal.json').read_text(encoding='utf-8'))
    if diagnostic_test:
        if acquisition.get('diagnostic_fixture') is not True or seal.get('diagnostic_fixture') is not True:
            raise ValueError('diagnostic test requires marked fixture provenance')
    elif (acquisition.get('provenance_kind') != 'native' or
          acquisition.get('diagnostic_fixture') is not False or
          seal.get('diagnostic_fixture') is not False):
        raise ValueError('original Native acquisition provenance required')
    source = attempt / 'capture' / 'crest-source'
    manifest_path = source / 'crest-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('case_id') != case:
        raise ValueError('selected saved source case differs')
    if omit_limit:
        manifest.pop('prescribed_limit_source', None)
    if not manifest.get('prescribed_limit_source'):
        raise ValueError('reviewed original prescribed limit source missing')
    source_proof = audit_media(source, manifest)
    if not all(source_proof['checks'][key] for key in
               ('native_source', 'all_participants', 'time_join',
                'full_video_decode', 'actual_pixels')):
        raise ValueError('saved source integrity check incomplete')
    if any(row['frame_count'] != 900 or not row['decoded_rgb24_sha256']
           for row in source_proof['camera_decodes'].values()):
        raise ValueError('actual four-view pixels incomplete')
    saved = json.loads(processing.read_text(encoding='utf-8'))
    if (saved.get('case_id') != case or saved.get('passed') is not True or
            saved.get('recorded_only') is not True or
            saved.get('originals_preserved') is not True or
            saved.get('timestamp_joins', {}).get('passed') is not True):
        raise ValueError('closed saved processing lacks original source checks')
    review_receipt = json.loads(review.read_text(encoding='utf-8'))
    reviewed = validate_review(case, _sha(manifest_path), source_proof,
                               review_receipt, diagnostic_test=diagnostic_test)
    return {'case_id': case, 'source_manifest_sha256': _sha(manifest_path),
            'saved_receipt_sha256': _sha(processing),
            'review_receipt_sha256': _sha(review),
            'frame_count': source_proof['frame_count'],
            'checks': {**source_proof['checks'],
                       'physical_completion': reviewed['physical_completion'] == 'met',
                       'visibility_review': reviewed['visibility'] == 'visible'},
            'reviewed_outcome': reviewed,
            'diagnostic_fixture': diagnostic_test,
            'physical_acceptance_claimed': not diagnostic_test and reviewed['physical_completion'] == 'met' and reviewed['visibility'] == 'visible',
            'legal_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('case')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--diagnostic-test', action='store_true')
    parser.add_argument('--omit-limit', action='store_true')
    args = parser.parse_args()
    print(json.dumps(accept(args.case, args.attempt, args.processing,
                            args.review, diagnostic_test=args.diagnostic_test,
                            omit_limit=args.omit_limit), sort_keys=True))


if __name__ == '__main__':
    main()

"""Independent NRS 484B.510 exact-case source and delivery audit.

A diagnostic fixture proves software plumbing only. Actual acceptance requires
an original Native attempt and separate source-cited review findings.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from original_source_contract import validate as validate_original


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case_id, diagnostic=False, attempt=None):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [item for item in manifest['cases'] if item['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact case')
    entry = entries[0]
    suffix = case_id.rsplit('__', 1)[-1]
    if not diagnostic:
        if attempt is None:
            raise ValueError('Original Native source required for delivery acceptance')
        source = validate_original(Path(attempt), Path(attempt) / 'original-review.json')
        if source['source_kind'] != 'original_native':
            raise ValueError('Original Native source required for delivery acceptance')
        if source['stopped_in_zone_frames'] < 1:
            raise ValueError('Physical restricted-zone stop absent from original source')
        if suffix in ('stop_only', 'stand_only') and source['moving_after_departure_frames'] < 1:
            raise ValueError('Original departure movement absent')
        if source['sign_authority_review'] != 'verified':
            raise ValueError('Original sign authority review remains unverified')
        for name in ('subject_purpose', 'actual_passenger_loading', 'waiting_driver_restricted_purpose', 'interference', 'temporary_stop'):
            if source[name]['status'] == 'unverified':
                raise ValueError('Original source review remains unverified: ' + name)
        return {'case_id': case_id, 'source_kind': 'original_native', 'physical_source_check': True,
                'legal_verdict': None, 'source_review_sha256': source['review_sha256']}
    source_dir = HERE / 'selected-source' / suffix
    capture = json.loads((source_dir / 'capture-manifest.json').read_text())
    review = json.loads((source_dir / 'original-review.json').read_text())
    actor = [json.loads(row) for row in (source_dir / 'actor-frames.jsonl').read_text().splitlines()]
    camera = [json.loads(row) for row in (source_dir / 'camera-frames.jsonl').read_text().splitlines()]
    if (capture.get('source_kind') != 'synthetic_fixture' or not capture.get('closed') or
            not capture.get('world_restored') or len(actor) != 600 or len(camera) != 600 or
            any(actor[i].get('frame') != i or camera[i].get('frame') != i for i in range(600))):
        raise ValueError('Diagnostic source closure or frame join incomplete')
    if review.get('case_id') != case_id:
        raise ValueError('Diagnostic review names another case')
    spec = entry.get('compatibility', {})
    receipt_path = HERE / spec.get('receipt', '')
    if not receipt_path.is_file() or sha(receipt_path) != spec.get('sha256'):
        raise ValueError('Selected public proof changed')
    receipt = json.loads(receipt_path.read_text())
    checks = {'actual_analysis', 'native_validation', 'mandatory_observations', 'lean_decoder',
              'final_decode', 'four_camera_sources', 'selected_measurements', 'negative_case_source'}
    if (receipt.get('case_id') != case_id or receipt.get('candidate_id') != 'primary' or
            receipt.get('construction_sha256') != entry['construction_sha256'] or
            receipt.get('passed') is not True or not checks <= set(receipt.get('checks', []))):
        raise ValueError('Current selected public proof incomplete')
    post = entry.get('post_capture', {})
    processing_path = HERE / post.get('processing_receipt', '')
    if not processing_path.is_file() or sha(processing_path) != post.get('processing_receipt_sha256'):
        raise ValueError('Selected saved-only proof changed')
    processing = json.loads(processing_path.read_text())
    if not (processing.get('passed') and processing.get('recorded_only') and processing.get('originals_preserved')):
        raise ValueError('Selected saved-only processing incomplete')
    physical_spec = entry.get('physical_preparation', {})
    physical_path = HERE / physical_spec.get('receipt', '')
    if not physical_path.is_file() or sha(physical_path) != physical_spec.get('sha256'):
        raise ValueError('Synthetic physical diagnostic changed')
    physical = json.loads(physical_path.read_text())
    if physical.get('original_native_observed') is not False:
        raise ValueError('Diagnostic fixture falsely claims original Native motion')
    return {'case_id': case_id, 'diagnostic_only': True, 'physical_acceptance': False,
            'legal_verdict': None, 'source_kind': 'synthetic_fixture', 'joined_frames': 600,
            'compatibility_sha256': sha(receipt_path), 'saved_processing_sha256': sha(processing_path),
            'actor_frames_sha256': sha(source_dir / 'actor-frames.jsonl'),
            'camera_frames_sha256': sha(source_dir / 'camera-frames.jsonl')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--attempt')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.diagnostic, args.attempt), sort_keys=True))

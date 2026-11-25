"""Independent production audit of sealed C188132 Native source and reviewed pixels."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from media_audit import audit_media
from overpass_source import audit_saved, sha

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _inside(root, name):
    path = (root / name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('missing or escaped original source: ' + name)
    return path


def audit(attempt, *, pixel_review, processing_receipt):
    root = Path(attempt).resolve()
    seal_path = _inside(root, 'capture-seal.json')
    seal = json.loads(seal_path.read_text())
    provenance = json.loads(_inside(root, 'acquisition-provenance.json').read_text())
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False or
            provenance.get('provenance_kind') != 'native' or
            provenance.get('diagnostic_fixture') is not False or
            seal.get('frames') != 900 or
            seal.get('restoration', {}).get('restored') is not True or
            seal.get('encoder_exit_codes') != {name: 0 for name in VIEWS}):
        raise ValueError('sealed original Native acquisition, full frames and restoration required')
    sources = seal.get('sources')
    if not isinstance(sources, dict) or not sources:
        raise ValueError('sealed Native source inventory required')
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(',', ':'),
                                        ensure_ascii=False).encode()).hexdigest()
    if digest != seal.get('source_digest'):
        raise ValueError('sealed Native source digest differs')
    required = {'scene.json', 'candidate-overpass.xodr', 'body-history.jsonl',
                'video_frames.jsonl', 'camera-frame-joins.jsonl', 'reviewed-site.json',
                'reviewed-site-source.txt', 'municipal-designation-source.txt',
                'original-sources.json', *(name + '.mkv' for name in VIEWS)}
    if not required <= set(sources):
        raise ValueError('sealed Native source inventory incomplete')
    for name, expected in sources.items():
        if sha(_inside(root, name)) != expected:
            raise ValueError('sealed Native source hash differs: ' + name)
    processing_path = Path(processing_receipt).resolve()
    if not processing_path.is_file():
        raise ValueError('saved processing receipt required')
    processing = json.loads(processing_path.read_text())
    if (processing.get('format') != 'worker-saved-processing' or
            processing.get('passed') is not True or processing.get('recorded_only') is not True or
            processing.get('originals_preserved') is not True or
            processing.get('missing_evidence') is not False or
            processing.get('timestamp_joins', {}).get('frames') != 900 or
            processing.get('timestamp_joins', {}).get('passed') is not True or
            any(processing.get('original_source_hashes', {}).get(name) != expected
                for name, expected in sources.items())):
        raise ValueError('saved physical processing does not bind sealed original sources')
    result_path = Path(processing.get('result', '')).resolve()
    if not result_path.is_relative_to(processing_path.parent) or not result_path.is_file():
        raise ValueError('saved physical result is missing or escaped')
    if sha(result_path) != processing.get('result_sha256'):
        raise ValueError('saved physical result hash differs')
    physical_result = json.loads(result_path.read_text())
    if (physical_result.get('provenance_kind') != 'native' or
            physical_result.get('diagnostic_fixture') is not False or
            physical_result.get('maneuver_completed') is not True or
            physical_result.get('physical_checks', {}).get('setup', {}).get('status') != 'met' or
            physical_result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met'):
        raise ValueError('original saved physical completion is not met')
    for name, expected in physical_result['physical_checks']['maneuver'].get('sources', {}).items():
        if name in sources and expected != sources[name]:
            raise ValueError('physical result source differs from sealed original: ' + name)
    original = audit_saved(root)
    media = audit_media(root)
    if media['frames'] != seal['frames']:
        raise ValueError('media and seal frame counts differ')
    case_id = original['measurement']['case_id']
    if physical_result.get('case_id') != case_id or processing.get('case_id') != case_id:
        raise ValueError('saved physical case identity differs')
    if media['case_id'] != case_id:
        raise ValueError('media and Native case identity differ')
    review_path = Path(pixel_review).resolve()
    if not review_path.is_file():
        raise ValueError('independent original pixel review required')
    review = json.loads(review_path.read_text())
    if (review.get('format') != 'c188132-original-pixel-review-v1' or
            review.get('provenance_kind') != 'original_review' or
            review.get('case_id') != case_id or
            review.get('capture_seal_sha256') != sha(seal_path) or
            not review.get('reviewer') or not review.get('source_method')):
        raise ValueError('pixel review is absent, synthetic or bound to another capture')
    observations = review.get('observations', {})
    for name in VIEWS:
        item = observations.get(name)
        if (not isinstance(item, dict) or item.get('video_sha256') != media['cameras'][name]['sha256'] or
                item.get('original_frames_reviewed') != 900 or
                item.get('pedestrian_visible') is not True or
                item.get('roadway_vehicles_visible') is not True or
                item.get('overpass_structure_visible') is not True):
            raise ValueError('original pixel visibility review incomplete: ' + name)
    physical = review.get('physical_review', {})
    if (physical.get('provided_overhead_crossing') is not True or
            physical.get('usable_deck_access') is not True or
            physical.get('pedestrian_crossing_completed') is not True or
            physical.get('all_roadway_vehicles_reviewed') is not True or
            physical.get('reviewed_site_sha256') != original['source_hashes']['site_review']):
        raise ValueError('original physical completion review incomplete')
    return {'format': 'worker-delivery-audit', 'case_id': case_id,
            'capture_seal_sha256': sha(seal_path), 'source_digest': digest,
            'pixel_review_sha256': sha(review_path), 'frame_count': 900,
            'processing_receipt_sha256': sha(processing_path),
            'physical_result_sha256': sha(result_path),
            'measurement': original['measurement'],
            'checks': {'native_source': True, 'all_participants': True,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': True, 'physical_completion': True},
            'video_sha256': {name: media['cameras'][name]['sha256'] for name in VIEWS},
            'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--pixel-review', required=True)
    parser.add_argument('--processing-receipt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, pixel_review=args.pixel_review,
                           processing_receipt=args.processing_receipt), indent=2))


if __name__ == '__main__':
    main()

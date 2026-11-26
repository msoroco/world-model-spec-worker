"""Bind an independent flagger/zone review to sealed original sources.

This checks provenance and review completeness. A signed review does not by
itself establish physical completion or a legal outcome.
"""

import json
from pathlib import Path
import argparse

from measure_original import CAMERAS, REVIEW_COPIES, measure


OBSERVATIONS = ('flagger_identity', 'signal_stop', 'signal_release',
                'signal_governs_approach', 'zone_markings')


def review(attempt, case_id, receipt_path):
    attempt = Path(attempt)
    receipt = json.loads(Path(receipt_path).read_text())
    measured = measure(attempt, case_id)
    seal = json.loads((attempt / 'captured-source-hashes.json').read_text())
    if (receipt.get('format') != 'c183370-original-review-v1' or
            receipt.get('case_id') != case_id or
            receipt.get('source_seal_sha256') != measured['source_seal_sha256'] or
            receipt.get('frame_count') != 600 or
            receipt.get('rate_hz') != 20 or
            receipt.get('source_kind') not in
            ('original_pixel_review', 'synthetic_structural_review') or
            not isinstance(receipt.get('reviewer'), str) or
            not receipt['reviewer'].strip()):
        raise ValueError('Independent original review identity or source seal differs')
    bound = {name: seal['sha256'][name] for name in
             list(REVIEW_COPIES.values()) + [camera + '.mkv' for camera in CAMERAS]}
    if receipt.get('reviewed_sha256') != bound:
        raise ValueError('Independent review source hashes differ')
    observations = receipt.get('observations')
    if not isinstance(observations, dict) or set(observations) != set(OBSERVATIONS):
        raise ValueError('Independent flagger and zone observations incomplete')
    for name in OBSERVATIONS:
        item = observations[name]
        if (not isinstance(item, dict) or
                item.get('camera') not in CAMERAS or
                type(item.get('video_frame')) is not int or
                not 0 <= item['video_frame'] < 600 or
                not isinstance(item.get('observed'), bool) or
                not isinstance(item.get('note'), str) or
                not item['note'].strip()):
            raise ValueError('Independent review observation invalid: ' + name)
        if name == 'signal_stop' and not 100 <= item['video_frame'] < 300:
            raise ValueError('Reviewed stop signal outside requested interval')
        if name == 'signal_release' and item['video_frame'] < 300:
            raise ValueError('Reviewed release signal before requested release')
    if receipt['source_kind'] == 'synthetic_structural_review':
        return {'case_id': case_id, 'source_seal_sha256':
                measured['source_seal_sha256'], 'binding_passed': True,
                'original_pixel_reviewed': False, 'physical_completion': None,
                'legal_verdict': None}
    if not all(observations[name]['observed'] for name in OBSERVATIONS):
        raise ValueError('Original flagger or zone observation unresolved')
    return {'case_id': case_id, 'source_seal_sha256':
            measured['source_seal_sha256'], 'binding_passed': True,
            'review_receipt_declares_original_observations': True,
            'original_pixel_reviewed': None, 'physical_completion': None,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--receipt', required=True)
    args = parser.parse_args()
    print(json.dumps(review(args.attempt, args.case, args.receipt), sort_keys=True))

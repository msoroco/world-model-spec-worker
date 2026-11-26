"""Independent saved comparison of designated-place body overlap."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_saved_packet import build, packet_from_attempt
from physical_check import assess
from saved_measure import _sources

def audit(inside, outside, inside_attempt, outside_attempt):
    a = json.loads(Path(inside).read_text())
    b = json.loads(Path(outside).read_text())
    if any(item.get('format') != 'worker-designated-stop-saved-measurement'
           for item in (a, b)):
        raise ValueError('Missing saved source-bound measurement')
    for saved, attempt in ((a, inside_attempt), (b, outside_attempt)):
        root = Path(attempt)
        if not root.is_dir() or saved.get('original_source_hashes') != _sources(root) or \
                saved.get('measurement') != build(root) or \
                saved.get('physical_check') != assess(packet_from_attempt(root)):
            raise ValueError('Saved measurement differs from original acquisition')
    if a.get('comparison_condition') != 'condition_a' or \
            b.get('comparison_condition') != 'condition_b' or \
            a.get('activity_mode_request') != b.get('activity_mode_request'):
        raise ValueError('Comparison identities or activity differ')
    if a.get('case_id', '').rsplit('condition_a', 1)[0] != \
            b.get('case_id', '').rsplit('condition_b', 1)[0]:
        raise ValueError('Comparison exact case families differ')
    ma, mb = a.get('measurement', {}), b.get('measurement', {})
    if ma.get('frames') != mb.get('frames') or ma.get('frames') != 600 or \
            ma.get('rate_hz') != mb.get('rate_hz') or ma.get('rate_hz') != 20:
        raise ValueError('Comparison frame or rate contract differs')
    fixed = ('device', 'designation', 'map', 'person_activity', 'traffic_direction')
    hashes_a, hashes_b = ma.get('source_hashes', {}), mb.get('source_hashes', {})
    if any(not hashes_a.get(name) or hashes_a[name] != hashes_b.get(name)
           for name in fixed):
        raise ValueError('Fixed original device, place or context source differs')
    if not ma.get('rest_frames') or not mb.get('rest_frames'):
        raise ValueError('Original rest intervals missing')
    if a['physical_check']['status'] != 'met' or b['physical_check']['status'] != 'met':
        raise ValueError('Original physical approach and rest missing')
    if ma.get('rest_and_body_overlap_frames', 0) <= 0 or \
            mb.get('rest_and_body_overlap_frames') != 0:
        raise ValueError('Deliberate designated-place body-overlap difference absent')
    if a.get('legal_verdict_claimed') or b.get('legal_verdict_claimed') or \
            a.get('physical_completion_claimed') or b.get('physical_completion_claimed'):
        raise ValueError('Comparison cannot assert legal or physical acceptance')
    return {'format': 'worker-designated-place-comparison-audit',
            'case_ids': [a['case_id'], b['case_id']],
            'activity_mode_request': a['activity_mode_request'],
            'fixed_original_source_hashes': {name: hashes_a[name] for name in fixed},
            'inside_rest_overlap_frames': ma['rest_and_body_overlap_frames'],
            'outside_rest_overlap_frames': mb['rest_and_body_overlap_frames'],
            'comparison_isolated': True, 'legal_verdict_claimed': False,
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--inside', required=True)
    parser.add_argument('--outside', required=True)
    parser.add_argument('--inside-attempt', required=True)
    parser.add_argument('--outside-attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.inside, args.outside,
                           args.inside_attempt, args.outside_attempt),
                     indent=2, sort_keys=True))

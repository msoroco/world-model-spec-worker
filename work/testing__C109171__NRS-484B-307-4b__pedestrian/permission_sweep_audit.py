"""Source-bound pedestrian device applicability and entry audit.

The audit records cited provision review and measured indication/entry. It does
not infer legal permission from an aspect label or a synthetic diagnostic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_scene import SourceError
from permission_applicability import PROVISIONS, source, validate as validate_review
from saved_measurement import ASSIGNMENT, measure_saved


def audit(root, case_id, site_ref, review_ref, events_ref, expected_frames=900,
          focus_provision_id=None):
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id == suffix or suffix not in (
            'arrow_wait', 'arrow_early_entry', 'arrow_walk_entry', 'arrow_walk_wait',
            'permission_applicability-0000', 'permission_applicability-0001',
            'permission_applicability-0002', 'permission_applicability-0003'):
        raise SourceError('unknown exact pedestrian case')
    if suffix.startswith('permission_applicability-'):
        index = int(suffix.rsplit('-', 1)[-1])
        if focus_provision_id != PROVISIONS[index]:
            raise SourceError('focused provision does not match exact sweep case')
    elif focus_provision_id is not None and focus_provision_id not in PROVISIONS:
        raise SourceError('unknown focused provision')
    checked = validate_review(root, site_ref, review_ref)
    review = json.loads(source(root, review_ref).read_text(encoding='utf-8'))
    measured = measure_saved(root, site_ref, events_ref, case_id, expected_frames)
    if checked['site_sha256'] != measured['original_site_sha256']:
        raise SourceError('review and measurement original site differ')
    if checked['provision_ids'] != list(PROVISIONS):
        raise SourceError('cited provision coverage incomplete')
    return {
        'format': 'c109171-permission-sweep-audit-v1',
        'case_id': case_id,
        'site_sha256': checked['site_sha256'],
        'review_sha256': checked['review_sha256'],
        'events_sha256': measured['original_events_sha256'],
        'provision_ids': checked['provision_ids'],
        'focus_provision_id': focus_provision_id,
        'focus_applicability': next((row['applicability'] for row in review['provisions']
                                     if row['provision_id'] == focus_provision_id), None),
        'unresolved_provisions': checked['unresolved_provisions'],
        'measured_first_highway_entry': measured['first_highway_entry'],
        'measured_walk_first_frame': measured['separate_walk_first_frame'],
        'measured_sole_green_arrow_frames': measured['sole_green_arrow_frames'],
        'frame_count': measured['frame_count'],
        'permission_at_entry': None,
        'legal_verdict': None,
        'physical_acceptance': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--site-ref', type=Path, required=True)
    parser.add_argument('--review-ref', type=Path, required=True)
    parser.add_argument('--events-ref', type=Path, required=True)
    parser.add_argument('--expected-frames', type=int, default=900)
    parser.add_argument('--focus-provision-id')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    def ref(path):
        return json.loads(path.read_text(encoding='utf-8'))
    result = audit(args.attempt, args.case_id, ref(args.site_ref),
                   ref(args.review_ref), ref(args.events_ref), args.expected_frames,
                   args.focus_provision_id)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

"""Independent saved original comparison for the three exact crossing pairs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from comparison_audit import audit_pair
from original_pixel_audit import audit as audit_pixels, sha
from reviewed_site import audit_reviewed_site
from saved_measurement import read_attempt

FIXED_CONFIG = ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras')
FIXED_SITE_FACTS = ('starting_curb_xy_m', 'opposite_curb_xy_m',
                    'roadway_highway_public_use', 'governing_control')


def read(path):
    return json.loads(Path(path).read_text())


def audit(comparison_id, left_attempt, right_attempt, left_review, right_review,
          *, diagnostic=False, package=None):
    package = Path(package or Path(__file__).resolve().parent).resolve()
    assignment = package.name
    plan = read(package / 'case-plan.json')
    pairs = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    if len(pairs) != 1 or len(pairs[0]['case_ids']) != 2:
        raise ValueError('unreviewed exact comparison')
    case_ids = pairs[0]['case_ids']
    attempts = [Path(left_attempt).resolve(), Path(right_attempt).resolve()]
    if attempts[0] == attempts[1]:
        raise ValueError('comparison requires two independent attempts')
    reviews = [left_review, right_review]
    scenes, configs, measurements, pixel_receipts, site_receipts = [], [], [], [], []
    for case_id, attempt, review in zip(case_ids, attempts, reviews):
        if not case_id.startswith(assignment + '__'):
            raise ValueError('comparison case belongs to another assignment')
        short = case_id.removeprefix(assignment + '__')
        exact = package / 'cases' / short
        for name in ('scene.json', 'config.json'):
            if sha(exact / name) != sha(attempt / name):
                raise ValueError('saved attempt differs from exact case ' + name)
        scene = read(exact / 'scene.json')
        config = read(exact / 'config.json')
        measured = read_attempt(attempt)
        if measured['case_id'] != case_id:
            raise ValueError('saved measurement case differs')
        pixel = audit_pixels(attempt, review, case_id, diagnostic=diagnostic)
        if not diagnostic and pixel.get('passed') is not True:
            raise ValueError('independent Native pixel review incomplete')
        scenes.append(scene)
        configs.append(config)
        measurements.append(measured)
        pixel_receipts.append(pixel)
        if not diagnostic:
            site = read(attempt / 'reviewed-site-audit.json')
            if site.get('case_id') != case_id:
                raise ValueError('reviewed site case differs')
            if site != audit_reviewed_site(scene, attempt):
                raise ValueError('reviewed site receipt differs from original documents')
            site_receipts.append(site)
    controlled = audit_pair(comparison_id, *scenes)
    if any(configs[0].get(key) != configs[1].get(key) for key in FIXED_CONFIG):
        raise ValueError('comparison fixed capture condition changed')
    if diagnostic:
        if any(not measured['diagnostic_fixture'] for measured in measurements):
            raise ValueError('comparison diagnostic provenance differs')
        status = 'software_diagnostic_only'
    else:
        if any(measured['diagnostic_fixture'] for measured in measurements):
            raise ValueError('original Native comparison required')
        if any(pixel['original_camera_frames'] != 400 for pixel in pixel_receipts):
            raise ValueError('complete original Native comparison missing')
        left_refs, right_refs = (site['source_refs'] for site in site_receipts)
        for fact in FIXED_SITE_FACTS + ('crosswalk_boundaries_xy_m',):
            for refs in (left_refs, right_refs):
                digest = refs.get(fact, {}).get('sha256')
                if not isinstance(digest, str) or re.fullmatch(r'[0-9a-f]{64}', digest) is None:
                    raise ValueError('comparison reviewed site source missing: ' + fact)
        for fact in FIXED_SITE_FACTS:
            if left_refs[fact]['sha256'] != right_refs[fact]['sha256']:
                raise ValueError('comparison fixed reviewed site source changed: ' + fact)
        if comparison_id != 'outside_vs_crosswalk_exception':
            if left_refs['crosswalk_boundaries_xy_m']['sha256'] != right_refs['crosswalk_boundaries_xy_m']['sha256']:
                raise ValueError('comparison fixed crosswalk source changed')
        status = 'native_originals_reviewed'
    return {'format': 'worker-pedestrian-original-comparison-audit',
            'assignment_id': assignment, 'comparison_id': comparison_id,
            'case_ids': case_ids, 'status': status, 'passed': not diagnostic,
            'scene_difference': controlled['changed_fields'],
            'attempt_source_hashes': [measured['sources_sha256'] for measured in measurements],
            'pixel_review_sha256': [receipt['source_review_sha256'] for receipt in pixel_receipts],
            'plan_sha256': sha(package / 'case-plan.json'),
            'physical_acceptance_claimed': False, 'legal_verdict': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--left-review', required=True)
    parser.add_argument('--right-review', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    receipt = audit(args.comparison, args.left_attempt, args.right_attempt,
                    args.left_review, args.right_review, diagnostic=args.diagnostic)
    Path(args.output).write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'comparison_id': args.comparison, 'status': receipt['status']}))


if __name__ == '__main__':
    main()

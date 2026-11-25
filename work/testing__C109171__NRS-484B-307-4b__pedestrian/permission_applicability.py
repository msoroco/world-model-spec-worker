"""Check a reviewed, source sealed 484B.283 applicability packet.

This is a provenance check. It does not decide whether an observed indication
actually granted permission to a particular pedestrian at a particular time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_scene import SourceError, verify_site


PROVISIONS = tuple(f'NRS-484B-283-1d{i}' for i in range(1, 5))


def require(condition, message):
    if not condition:
        raise SourceError(message)


def source(root, ref):
    require(isinstance(ref, dict) and isinstance(ref.get('path'), str) and
            isinstance(ref.get('sha256'), str), 'source reference incomplete')
    root = Path(root).resolve()
    path = (root / ref['path']).resolve()
    require(path.is_relative_to(root) and path.is_file(), 'review source missing or escapes attempt')
    require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'],
            'review source hash differs')
    return path


def validate(root, site_ref, review_ref):
    """Require four cited provisions and an explicit, original device review."""
    site = json.loads(source(root, site_ref).read_text(encoding='utf-8'))
    verify_site(site, root)
    review = json.loads(source(root, review_ref).read_text(encoding='utf-8'))
    require(review.get('format') == 'c109171-permission-applicability-review-v1',
            'permission review format differs')
    require(review.get('site_sha256') == site_ref['sha256'] and
            review.get('cell_id') == 'C109171' and
            review.get('pedestrian_route_id') == site['pedestrian_route_id'] and
            review.get('pedestrian_device_id') == site['pedestrian_device_id'],
            'permission review does not bind original site and device')
    require(review.get('vehicle_head_id') == site['official_vehicle_head_id'] and
            review.get('vehicle_head_id') != review.get('pedestrian_device_id'),
            'permission review conflates vehicle and pedestrian heads')
    rows = review.get('provisions')
    require(isinstance(rows, list) and len(rows) == len(PROVISIONS),
            'all four cited permission provisions require review')
    require([row.get('provision_id') for row in rows] == list(PROVISIONS),
            'cited permission provision order or identity differs')
    for row in rows:
        require(row.get('applicability') in ('applies', 'does_not_apply', 'unresolved'),
                'permission applicability disposition missing')
        require(isinstance(row.get('reason'), str) and row['reason'].strip(),
                'permission applicability reason missing')
        law = source(root, row.get('law_source'))
        require(row['provision_id'] in law.read_text(encoding='utf-8'),
                'cited provision not in reviewed law source')
        device = source(root, row.get('device_source'))
        require(row['device_source']['sha256'] == next(
            ref['sha256'] for ref in site['original_sources']
            if ref['path'] == site['pedestrian_device_source_path']),
            'reviewed permission device is not the original governing device')
        require(device.name == Path(site['pedestrian_device_source_path']).name,
                'reviewed permission device path differs')
    require(review.get('permission_at_entry') is None,
            'source review must not assert permission at entry before capture')
    return {'format': 'c109171-permission-review-preflight-v1',
            'site_sha256': site_ref['sha256'], 'review_sha256': review_ref['sha256'],
            'provision_ids': list(PROVISIONS),
            'unresolved_provisions': [row['provision_id'] for row in rows
                                      if row['applicability'] == 'unresolved'],
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--site-ref', type=Path, required=True)
    parser.add_argument('--review-ref', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    checked = validate(args.attempt,
                       json.loads(args.site_ref.read_text(encoding='utf-8')),
                       json.loads(args.review_ref.read_text(encoding='utf-8')))
    args.output.write_text(json.dumps(checked, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

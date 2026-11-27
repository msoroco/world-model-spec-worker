"""Join original road/device readback to independently cited authority and extent.

The fields are observations and source assertions. A fixture may test this join,
but it cannot make a synthetic sign official or prove legal narrowness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

FIELDS = ('highway', 'narrow_designation', 'official_authority',
          'device_erection', 'device_content', 'governed_extent')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def join(attempt, case_id):
    attempt = Path(attempt)
    native = json.loads((attempt / 'road-context.json').read_text())
    review = json.loads((attempt / 'road-review.json').read_text())
    require(review.get('case_id') == case_id and
            review.get('native_context_sha256') == sha(attempt / 'road-context.json'),
            'Independent road review binds another case or Native context')
    require(native.get('case_id') == case_id and native.get('map_sha256') == sha(attempt / 'road.xodr'),
            'Original Native road readback differs')
    sources = review.get('sources')
    require(isinstance(sources, dict) and set(sources) == set(FIELDS),
            'Independent narrow-road and device sources missing')
    hashes = {}
    for name, ref in sources.items():
        relative = 'source_context/' + name + '.txt'
        require(ref.get('path') == relative and (attempt / relative).is_file(),
                'Missing required source: ' + relative)
        digest = sha(attempt / relative)
        require(ref.get('sha256') == digest, 'Independent road source hash differs: ' + name)
        hashes[name] = digest
    for key in ('roadway_is_highway', 'narrow_highway_designated',
                'device_is_official', 'device_erected', 'device_prohibits_parking'):
        require(type(review.get(key)) is bool, 'Independent road assertion missing: ' + key)
    require(review['roadway_is_highway'] and review['narrow_highway_designated'] and
            review['device_is_official'] and review['device_erected'] and
            review['device_prohibits_parking'],
            'Source review does not establish narrow-highway prohibitory-device activation')
    require(review.get('device_id') == '490' and review.get('governed_road_id') == '1',
            'Device/road governance differs from Native readback')
    extent = review.get('governed_extent_xyxy_m')
    require(isinstance(extent, list) and len(extent) == 4 and
            extent[0] < extent[2] and extent[1] < extent[3],
            'Independent governed extent missing')
    width = review.get('measured_road_width_m')
    require(type(width) in (float, int) and width > 0,
            'Original road width measurement missing')
    require(review.get('narrow_section_source_id') and
            review.get('device_official_source_id'),
            'Independent road/device source identities missing')
    return {'assignment_id': native['assignment_id'],
            'source_kind': ('synthetic_native_sample' if review.get('synthetic_diagnostic')
                            else 'native_saved_sample'),
            'road_type': 'highway',
            'narrow_section_source_id': review['narrow_section_source_id'],
            'measured_road_width_m': width,
            'device_id': review['device_id'],
            'device_erected': review['device_erected'],
            'device_official_source_id': review['device_official_source_id'],
            'device_prohibits_parking': review['device_prohibits_parking'],
            'governed_extent_xyxy_m': extent,
            'source_sha256': hashes,
            'physical_or_legal_acceptance': False}

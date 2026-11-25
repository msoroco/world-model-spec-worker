"""Join the original road readback to separately sourced legal context.

The review records observations and provenance, never a legal conclusion.
"""
import hashlib
import json
from pathlib import Path


FIELDS = ('one_way_designation', 'street_boundary', 'device_inventory',
          'device_authority', 'device_content', 'device_erection', 'device_governance')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def join(attempt, case_id, permission):
    attempt = Path(attempt)
    native = json.loads((attempt / 'road-context.json').read_text())
    review = json.loads((attempt / 'road-review.json').read_text())
    if review.get('case_id') != case_id or review.get('native_context_sha256') != sha(attempt / 'road-context.json'):
        raise ValueError('Independent road review binds another case or Native context')
    if native.get('permission_device_requested') is not permission:
        raise ValueError('Native device request differs from selected case')
    context = dict(native)
    context['source_kind'] = ('synthetic_native_sample' if review.get('synthetic_diagnostic')
                              else 'native_saved_sample')
    context['map_source_sha256'] = sha(attempt / 'road.xodr')
    for name in FIELDS:
        record = review.get(name)
        if name in FIELDS[3:] and not permission:
            context[name + '_source_sha256'] = None
            continue
        if not isinstance(record, dict):
            raise ValueError('Independent road source missing: ' + name)
        path = record.get('path')
        if path != 'source_context/' + name + '.txt' or not (attempt / path).is_file():
            raise ValueError('Independent road source missing: ' + name)
        if record.get('sha256') != sha(attempt / path):
            raise ValueError('Independent road source hash differs: ' + name)
        context[name + '_source_sha256'] = record['sha256']
    required = ('roadway_is_laned', 'roadway_is_one_way', 'permission_device_present',
                'device_official', 'device_erected',
                'notice_permits_left_standing_or_parking')
    if any(type(review.get(key)) is not bool for key in required):
        raise ValueError('Independent road assertion missing')
    if review['permission_device_present'] is not permission:
        raise ValueError('Independent permission inventory differs')
    for key in required:
        context[key] = review[key]
    context['device_governs_road_id'] = review.get('device_governs_road_id')
    context['physical_sign_pixels_verified'] = False
    context['operator_source_review_required'] = True
    return context

"""Independent source-bound audit of the exact other-first response pair."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_history_capture import CAMERAS, _retained_file, audit_media
from saved_crossing import ASSIGNMENT, compare, measure


FIXED_SITE = (
    'assignment_id', 'cell_id', 'control', 'maneuver', 'map_sha256',
    'crossing_id', 'roadway_id', 'ego_highway', 'other_highway',
    'approach_relation', 'ego_side', 'other_side',
    'official_yield_sign_present', 'yield_sign_controls_intersection',
    'subsection_4_reviewed', 'subsection_4_source_citation',
    'intersection_polygon_xy_m', 'ego_route', 'other_route',
    'ego_lane', 'other_lane', 'ego_blueprint', 'other_blueprint',
    'release_s', 'other_release_s', 'camera_dimensions', 'camera_poses',
    'camera_mounts', 'device_source', 'highway_source',
)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _case(attempt, saved_path, expected):
    attempt = Path(attempt)
    saved_path = Path(saved_path)
    if not saved_path.is_file() or saved_path.is_symlink():
        raise ValueError('sealed saved result missing')
    saved = json.loads(saved_path.read_text(encoding='utf-8'))
    if saved.get('format') != 'worker-c125763-2501-saved-v1' or saved.get('case_id') != expected:
        raise ValueError('exact saved case identity differs')
    source_manifest = _retained_file(attempt, 'source-manifest.json')
    if saved.get('source_manifest_sha256') != _sha(source_manifest):
        raise ValueError('saved original manifest binding changed')
    site = json.loads(_retained_file(attempt, 'site-context.json').read_text(encoding='utf-8'))
    measurement = measure(attempt)
    if saved.get('crossing_measurement') != measurement:
        raise ValueError('saved crossing measurement changed')
    if saved.get('source_sha256') != measurement['source_sha256']:
        raise ValueError('saved original source hashes changed')
    dimensions = site.get('camera_dimensions')
    if not isinstance(dimensions, dict) or set(dimensions) != set(CAMERAS):
        raise ValueError('four source-bound camera dimensions required')
    media = audit_media(attempt, camera_dimensions=dimensions)
    if saved.get('camera_audit') != media:
        raise ValueError('saved four-camera audit differs')
    return site, measurement, _sha(saved_path), _sha(source_manifest)


def audit(precedence_attempt, precedence_result, advance_attempt, advance_result):
    before = _case(precedence_attempt, precedence_result, ASSIGNMENT + '__precedence')
    after = _case(advance_attempt, advance_result, ASSIGNMENT + '__advance')
    first_site, first_measure, first_saved_sha, first_manifest_sha = before
    second_site, second_measure, second_saved_sha, second_manifest_sha = after
    if first_manifest_sha == second_manifest_sha:
        raise ValueError('two distinct sealed Native attempts required')
    for field in FIXED_SITE:
        if first_site.get(field) != second_site.get(field):
            raise ValueError('fixed original comparison site changed: ' + field)
    if first_measure['other_cleared_before_ego_entry'] is not True or \
            second_measure['other_cleared_before_ego_entry'] is not False:
        raise ValueError('requested precedence and advance clearance orders differ')
    comparison = compare(first_measure, second_measure)
    return {
        'format': 'worker-c125763-2501-saved-comparison-v1',
        'assignment_id': ASSIGNMENT,
        'comparison_id': 'official_yield_precedence',
        'case_ids': [ASSIGNMENT + '__precedence', ASSIGNMENT + '__advance'],
        'saved_result_sha256': [first_saved_sha, second_saved_sha],
        'source_manifest_sha256': [first_manifest_sha, second_manifest_sha],
        'measured_comparison': comparison,
        'official_device_exception_unresolved': True,
        'physical_acceptance': False,
        'legal_verdict_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--precedence-attempt', required=True)
    parser.add_argument('--precedence-result', required=True)
    parser.add_argument('--advance-attempt', required=True)
    parser.add_argument('--advance-result', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.precedence_attempt, args.precedence_result,
                   args.advance_attempt, args.advance_result)
    output = Path(args.output)
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

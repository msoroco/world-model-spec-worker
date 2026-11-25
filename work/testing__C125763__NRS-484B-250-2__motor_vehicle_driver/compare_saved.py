"""Independently compare the three source-sealed crossing timing captures."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from crossing_timing import measure
from native_history_capture import CAMERAS, audit_media


ASSIGNMENT = 'testing__C125763__NRS-484B-250-2__motor_vehicle_driver'
PROBES = ('entry_below', 'entry_inside', 'entry_above')
FIXED = ('map_sha256', 'cell_id', 'control', 'ego_highway', 'other_highway',
         'approach_relation', 'ego_side', 'intersection_bounds_xy_m',
         'ego_route', 'other_route', 'ego_lane', 'other_lane',
         'ego_blueprint', 'other_blueprint', 'weather', 'camera_poses',
         'camera_mounts', 'camera_dimensions', 'device_source', 'highway_source',
         'release_s', 'ego_release_s')


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def compare(plan_path, spec_path):
    """Require exact planned cases, original sources and isolated release timing."""
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    spec = json.loads(Path(spec_path).read_text(encoding='utf-8'))
    if plan.get('assignment_id') != ASSIGNMENT:
        raise ValueError('wrong exact assignment plan')
    rows = [row for row in plan.get('comparisons', [])
            if row.get('comparison_id') == 'entry_timing_range']
    if len(rows) != 1:
        raise ValueError('exact timing comparison absent or duplicated')
    expected = rows[0]['case_ids']
    if (len(expected) != 3 or
            expected != [ASSIGNMENT + '__' + probe for probe in PROBES]):
        raise ValueError('planned timing cases differ')
    cases = spec.get('cases')
    if (spec.get('comparison_id') != 'entry_timing_range' or
            not isinstance(cases, list) or
            [row.get('case_id') for row in cases] != expected):
        raise ValueError('comparison source cases differ from plan')

    observed = []
    fixed = None
    release_s = []
    for probe, row in zip(PROBES, cases):
        attempt = Path(row['attempt'])
        result_path = Path(row['saved_result'])
        if _sha(result_path) != row.get('saved_result_sha256'):
            raise ValueError('saved result bytes changed: ' + probe)
        result = json.loads(result_path.read_text(encoding='utf-8'))
        manifest = attempt / 'source-manifest.json'
        if (_sha(manifest) != row.get('source_manifest_sha256') or
                result.get('source_manifest_sha256') != row['source_manifest_sha256']):
            raise ValueError('original source manifest differs: ' + probe)
        if (result.get('assignment_id') != ASSIGNMENT or
                result.get('probe_id') != probe or
                result.get('legal_verdict_claimed') is not False or
                result.get('physical_acceptance') is not False):
            raise ValueError('saved exact-case identity or claim differs: ' + probe)
        measured = measure(attempt)
        if result.get('timing') != measured:
            raise ValueError('saved measurement differs from original: ' + probe)
        site = json.loads((attempt / 'site-context.json').read_text(encoding='utf-8'))
        if (not isinstance(site.get('camera_dimensions'), dict) or
                set(site['camera_dimensions']) != set(CAMERAS)):
            raise ValueError('four original camera dimensions missing: ' + probe)
        media = audit_media(attempt, camera_dimensions=site['camera_dimensions'])
        if (result.get('camera_audit') != media or
                result.get('camera_coverage_verified') is not True or
                result.get('original_frame_count') != media['joined_original_frames']):
            raise ValueError('saved four-camera audit differs: ' + probe)
        current_fixed = {key: site.get(key) for key in FIXED}
        if any(value is None for value in current_fixed.values()):
            raise ValueError('fixed scene condition missing: ' + probe)
        if fixed is None:
            fixed = current_fixed
        elif fixed != current_fixed:
            raise ValueError('fixed scene conditions differ: ' + probe)
        releases = site.get('release_s')
        if (not isinstance(releases, dict) or set(releases) != set(PROBES) or
                not all(type(releases[name]) in (int, float) and releases[name] >= 0
                        for name in PROBES)):
            raise ValueError('three original release schedules missing: ' + probe)
        release_s.append(releases[probe])
        observed.append({'case_id': row['case_id'], 'source_manifest_sha256': _sha(manifest),
                         'saved_result_sha256': _sha(result_path),
                         'release_s': releases[probe],
                         'entry_difference_s': measured['intersection_entry_time_difference_s'],
                         'difference_bracket_s': measured['difference_bracket_s'],
                         'original_frames': media['joined_original_frames']})
    if len(set(release_s)) != 3:
        raise ValueError('deliberate release schedules are not distinct')
    return {'format': 'c125763-source-bound-comparison-v1',
            'comparison_id': 'entry_timing_range', 'case_ids': expected,
            'fixed_scene': fixed, 'observed': observed,
            'approximately_same_time': 'unresolved_judgment',
            'subsection_4_applicability': 'not_supported_by_fixed_yield_sign_cell',
            'legal_verdict_claimed': False, 'physical_acceptance': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=Path(__file__).with_name('case-plan.json'))
    parser.add_argument('--spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.plan, args.spec)
    if args.output.exists():
        raise FileExistsError(args.output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()

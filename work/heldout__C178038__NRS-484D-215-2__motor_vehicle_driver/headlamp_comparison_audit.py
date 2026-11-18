"""Compare retained source shaped headlamp cases without a legal outcome claim."""

import argparse
import hashlib
import json
from pathlib import Path

from headlamp_finalizer import analyze

PAIRS = {
    'distance_299_300': ('night_299_upper', 'night_300_upper', {'following_footprints.jsonl'}),
    'distance_300_301': ('night_300_upper', 'night_301_upper', {'following_footprints.jsonl'}),
    'distribution': ('night_299_upper', 'night_299_other', {'headlamp_readbacks.jsonl'}),
    'lighting_time': ('night_299_upper', 'day_299_upper', {'lighting_context.json', 'roadway_environment.jsonl'}),
    'shoulder': ('night_299_upper', 'shoulder_299_upper', {'roadway_environment.jsonl'}),
}
SOURCES = ('video_frames.jsonl', 'trace.jsonl', 'following_footprints.jsonl',
           'headlamp_readbacks.jsonl', 'roadway_environment.jsonl', 'lighting_context.json',
           'road.xodr', 'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    report = analyze(root)
    if report['case_id'] != config['selected_case_id']:
        raise ValueError('Selected case differs from original analysis')
    value = report['measurements']['headlamp_following_observation']['value']
    if not value['observations'] or not all(row['following_geometry'] for row in value['observations']):
        raise ValueError('Original following geometry missing')
    return config, report, value, {name: sha(root / name) for name in SOURCES}


def audit(comparison_id, left_root, right_root):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown headlamp comparison')
    left_name, right_name, allowed = PAIRS[comparison_id]
    lc, lr, lv, lh = saved(left_root)
    rc, rr, rv, rh = saved(right_root)
    if (lc['selected_case_id'].split('__')[-1], rc['selected_case_id'].split('__')[-1]) != (left_name, right_name):
        raise ValueError('Exact comparison case pair differs')
    changed = {name for name in SOURCES if lh[name] != rh[name]}
    if changed != allowed:
        raise ValueError('Fixed source differs or comparison variable did not change')
    left_observed, right_observed = lv['observations'][0], rv['observations'][0]
    if comparison_id.startswith('distance_'):
        if (lc['requested_gap_ft'] == rc['requested_gap_ft'] or
                lv['minimum_surface_gap_ft'] == rv['minimum_surface_gap_ft'] or
                left_observed['uppermost_distribution_readback'] != right_observed['uppermost_distribution_readback']):
            raise ValueError('Body gap comparison failed')
    elif comparison_id == 'distribution':
        if (lc['requested_gap_ft'] != rc['requested_gap_ft'] or
                left_observed['uppermost_distribution_readback'] == right_observed['uppermost_distribution_readback']):
            raise ValueError('Lamp distribution comparison failed')
    elif comparison_id == 'lighting_time':
        if (lc['requested_gap_ft'] != rc['requested_gap_ft'] or
                lv['lighting_time_applies'] == rv['lighting_time_applies']):
            raise ValueError('Lighting-time premise comparison failed')
    else:
        ll = {row['lane_type_readback'] for row in lr['roadway_environment_observations']}
        rl = {row['lane_type_readback'] for row in rr['roadway_environment_observations']}
        if (lc['requested_gap_ft'] != rc['requested_gap_ft'] or ll != {'Driving'} or rl != {'Shoulder'}):
            raise ValueError('Roadway-position comparison failed')
    return {'format': 'worker-headlamp-source-comparison-audit',
            'comparison_id': comparison_id,
            'case_ids': [lc['selected_case_id'], rc['selected_case_id']],
            'changed_original_sources': sorted(changed),
            'fixed_original_source_sha256': {name: lh[name] for name in SOURCES if name not in allowed},
            'requested_gap_ft': [lc['requested_gap_ft'], rc['requested_gap_ft']],
            'measured_minimum_surface_gap_ft': [lv['minimum_surface_gap_ft'], rv['minimum_surface_gap_ft']],
            'uppermost_distribution_readback': [left_observed['uppermost_distribution_readback'], right_observed['uppermost_distribution_readback']],
            'lighting_time_applies': [lv['lighting_time_applies'], rv['lighting_time_applies']],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison audit')
    output.write_text(json.dumps(audit(args.comparison, args.left, args.right), indent=2) + '\n')

"""Independent saved-source comparison checks for C136539 exposure scenes."""

import argparse
import hashlib
import json
from pathlib import Path

from endangerment_finalizer import analyze
from exposure_case_setup import case_settings


PAIRS = {
    'speed_sweep_low_mid': ('slow_person_exposure', 'moderate_person_exposure', 'speed_mps'),
    'speed_sweep_mid_high': ('moderate_person_exposure', 'fast_person_exposure', 'speed_mps'),
    'pedestrian_clearance': ('moderate_person_exposure', 'clearance_reference', 'outside_edge_m'),
    'property_clearance': ('property_near', 'property_far', 'outside_edge_m'),
}


def _saved(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    settings = case_settings(config)
    context_path = root / 'alley_context.json'
    road_path = root / 'road.xodr'
    context = json.loads(context_path.read_text())
    scene = {
        'map_name': context.get('native_map_name'),
        'road_id': context.get('road_id'),
        'context_sha256': hashlib.sha256(context_path.read_bytes()).hexdigest(),
        'road_sha256': hashlib.sha256(road_path.read_bytes()).hexdigest(),
    }
    if not scene['map_name'] or type(scene['road_id']) is not int or not road_path.is_file():
        raise ValueError('Saved scene provenance missing')
    report = analyze(root)
    observation = report['measurements']['person_or_property_exposure']['value']
    if {row['exposed_kind'] for row in observation['observations']} != {settings['exposed_kind']}:
        raise ValueError('Original exposed kind differs from exact setup')
    return settings, scene, observation


def audit(comparison_id, left_root, right_root):
    if comparison_id not in PAIRS:
        raise ValueError('Unknown exposure comparison')
    left_name, right_name, variable = PAIRS[comparison_id]
    left, left_scene, left_observed = _saved(left_root)
    right, right_scene, right_observed = _saved(right_root)
    if (left['case_id'].rsplit('__', 1)[-1], right['case_id'].rsplit('__', 1)[-1]) != (left_name, right_name):
        raise ValueError('Exact comparison case pair differs')
    for field in ('map_name', 'road_id', 'context_sha256', 'road_sha256'):
        if left_scene[field] != right_scene[field]:
            raise ValueError('Comparison fixed road geometry changed: ' + field)
    for field in ('speed_mps', 'outside_edge_m', 'exposed_kind'):
        if field == variable:
            if left[field] == right[field]:
                raise ValueError('Comparison requested variable did not differ')
        elif left[field] != right[field]:
            raise ValueError('Comparison fixed setting changed: ' + field)
    return {'format': 'worker-exposure-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': [left['case_id'], right['case_id']],
            'fixed_scene': {key: left_scene[key] for key in ('map_name', 'road_id', 'context_sha256', 'road_sha256')},
            'deliberate_difference': variable,
            'requested_values': [left[variable], right[variable]],
            'source_sha256': [left_observed['source_sha256'], right_observed['source_sha256']],
            'measured_minimum_surface_gap_m': [left_observed['minimum_surface_gap_m'], right_observed['minimum_surface_gap_m']],
            'measured_maximum_speed_mps': [left_observed['maximum_ego_speed_mps'], right_observed['maximum_ego_speed_mps']],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.left, args.right)
    path = Path(args.output)
    if path.exists():
        raise ValueError('Retain prior comparison audit')
    path.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()

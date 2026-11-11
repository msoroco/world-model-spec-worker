"""Independent saved-source comparison checks for C136539 exposure scenes."""

import argparse
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
    scene = json.loads((root / 'construction-probe.json').read_text())
    if scene.get('case_id') != settings['case_id'] or scene.get('exact_settings') != settings:
        raise ValueError('Exact construction/scene identity differs')
    if (not scene.get('map_name') or type(scene.get('road_id')) is not int or
            type(scene.get('lane_id')) is not int or scene['lane_id'] == 0):
        raise ValueError('Original scene provenance missing')
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
    for field in ('map_name', 'road_id', 'lane_id'):
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
            'fixed_scene': {key: left_scene[key] for key in ('map_name', 'road_id', 'lane_id')},
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

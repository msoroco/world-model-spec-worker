"""Independent exact saved-source comparison across C10364 alley cases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


PREFIX = 'heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver__'
GROUPS = {
    'person_speed_sweep': (['person_3mps', 'person_5mps', 'person_7mps'], 'target_speed_mps'),
    'property_speed_sweep': (['property_3mps', 'property_5mps', 'property_7mps'], 'target_speed_mps'),
    'protected_interest_geometry': (['person_5mps', 'property_5mps'], 'protected_interest'),
    'alley_pedestrian_offset_sweep': (['alley_gap_judgment_sweep-0000',
                                       'alley_gap_judgment_sweep-0001',
                                       'alley_gap_judgment_sweep-0002'], 'pedestrian_offset_m'),
}
FIXED = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
         'alley_direction', 'alley_width_m', 'alley_polygon_xy',
         'alley_polygon_source')
SOURCES = ('participant_footprints.jsonl', 'ego_motion.jsonl',
           'trace.jsonl', 'video_frames.jsonl')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def read_saved(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    report_path = root / 'analysis-report.json'
    report = json.loads(report_path.read_text())
    if report.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Exact comparison report identity differs')
    observed = report['measurements']['alley_original_exposure']['value']
    if any(observed.get('source_sha256', {}).get(name) != digest(root / name)
           for name in SOURCES):
        raise ValueError('Comparison original source hash differs')
    polygon = config['alley_polygon_source']
    if polygon['sha256'] != digest(root / polygon['path']):
        raise ValueError('Comparison alley polygon source hash differs')
    if (root / 'fixture-provenance.json').is_file():
        native_source = None
    else:
        original = root / 'alley-survey-original.json'
        verification = root / 'alley-survey-verification.json'
        seal = json.loads((root / 'capture-seal.json').read_text())
        manifest = json.loads(original.read_text())
        receipt = json.loads(verification.read_text())
        if (manifest.get('format') != 'worker-native-alley-survey-v1' or
                manifest.get('verified_alley') is not True or
                receipt.get('verified') is not True or
                receipt.get('operator_manifest_sha256') != digest(original) or
                receipt.get('map_name') != manifest.get('map_name') or
                receipt.get('opendrive_sha256') != manifest.get('opendrive_sha256') or
                receipt.get('polygon_xy') != manifest.get('polygon_xy') or
                seal.get('provenance_kind') != 'native' or
                seal.get('sources', {}).get(original.name) != digest(original) or
                seal.get('sources', {}).get(verification.name) != digest(verification)):
            raise ValueError('Comparison Native alley source differs')
        native_source = digest(original)
    if report.get('physical_acceptance_claimed') or report.get('legal_acceptance_claimed'):
        raise ValueError('Comparison source claims unsupported acceptance')
    return {'config': config, 'observed': observed,
            'report_sha256': digest(report_path),
            'native_source_sha256': native_source}


def audit(comparison_id, roots):
    if comparison_id not in GROUPS:
        raise ValueError('Unknown exact alley comparison')
    suffixes, variable = GROUPS[comparison_id]
    if len(roots) != len(suffixes):
        raise ValueError('Comparison source count differs')
    items = [read_saved(root) for root in roots]
    configs = [item['config'] for item in items]
    if [row['selected_case_id'] for row in configs] != [PREFIX + suffix for suffix in suffixes]:
        raise ValueError('Comparison exact case IDs or order differ')
    for key in FIXED:
        if any(config[key] != configs[0][key] for config in configs[1:]):
            raise ValueError('Comparison fixed condition differs: ' + key)
    native_sources = [item['native_source_sha256'] for item in items]
    if any(value != native_sources[0] for value in native_sources[1:]):
        raise ValueError('Comparison Native alley source differs across cases')
    for key in ('target_speed_mps', 'protected_interest', 'pedestrian_offset_m'):
        values = [config[key] for config in configs]
        if key == variable:
            if len(set(values)) != len(values):
                raise ValueError('Comparison deliberate variable did not differ: ' + key)
        elif any(value != values[0] for value in values[1:]):
            raise ValueError('Comparison fixed condition differs: ' + key)
    if variable == 'target_speed_mps' and [row[variable] for row in configs] != [3, 5, 7]:
        raise ValueError('Comparison requested speed order differs')
    if variable == 'pedestrian_offset_m' and [row[variable] for row in configs] != [1.5, 2.4, 1.95]:
        raise ValueError('Comparison authored offset setpoints differ')
    observed = [item['observed'] for item in items]
    speeds = [item['maximum_observed_speed_mps'] for item in observed]
    person_gaps = [item['minimum_pedestrian_gap_m'] for item in observed]
    property_gaps = [item['minimum_property_gap_m'] for item in observed]
    for values in (speeds, person_gaps, property_gaps):
        if any(type(value) not in (int, float) or value < 0 for value in values):
            raise ValueError('Comparison measured observable is missing')
    if variable == 'target_speed_mps':
        realized = speeds[0] < speeds[1] < speeds[2]
    elif variable == 'pedestrian_offset_m':
        # A lateral setpoint may not monotonically change actual body gap;
        # retain measurements without declaring a legal or physical judgment.
        realized = len(set(person_gaps)) == len(person_gaps)
    else:
        realized = person_gaps[0] < property_gaps[0] and property_gaps[1] < person_gaps[1]
    return {'format': 'worker-alley-source-comparison-audit',
            'comparison_id': comparison_id,
            'case_ids': [config['selected_case_id'] for config in configs],
            'fixed_conditions': {key: configs[0][key] for key in FIXED},
            'deliberate_difference': variable,
            'requested_values': [config[variable] for config in configs],
            'report_sha256': [item['report_sha256'] for item in items],
            'original_source_sha256': [item['source_sha256'] for item in observed],
            'native_alley_source_sha256': native_sources[0],
            'measured_maximum_speed_mps': speeds,
            'measured_minimum_pedestrian_gap_m': person_gaps,
            'measured_minimum_property_gap_m': property_gaps,
            'comparison_complete': realized,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=GROUPS)
    parser.add_argument('--attempts', nargs='+', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.attempts), indent=2))


if __name__ == '__main__':
    main()

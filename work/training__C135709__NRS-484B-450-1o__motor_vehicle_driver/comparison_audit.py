"""Independent fixed-condition and parking-frontage contrast audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(comparison_id, processing_specs, omit_case=None):
    plan = read(HERE / 'case-plan.json')
    comparison = next((x for x in plan['comparisons'] if x['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown comparison')
    paths = dict(item.split('=', 1) for item in processing_specs)
    if set(paths) != set(comparison['case_ids']) or omit_case:
        raise ValueError('Missing comparison case: ' + str(omit_case or sorted(set(comparison['case_ids']) - set(paths))))
    manifest = read(HERE / 'execution-manifest.json')
    observations = []
    for case in comparison['case_ids']:
        selected = next(row for row in manifest['cases'] if row['case_id'] == case)
        saved = read(paths[case])
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
                saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
                saved.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Selected comparison source differs')
        stage = Path(saved['analysis_directory'])
        config = read(stage / 'config.json')
        report = read(stage / 'analysis-report.json')
        measured = report.get('measurements', {}).get('parking_adjacency', {})
        if measured.get('method') != 'measured':
            raise ValueError('Comparison lacks source-bound parking measurement')
        for name, digest in measured.get('sources', {}).items():
            if digest != sha(stage / name):
                raise ValueError('Comparison source changed: ' + name)
        observations.append((case, config, measured['value'], stage, sha(stage / 'analysis-report.json')))
    configs = [row[1] for row in observations]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'source_packets'):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError('Comparison fixed condition changed: ' + field)
    if [config['parking_case'] for config in configs] != ['away', 'beside']:
        raise ValueError('Parking frontage station request contrast changed')
    overlaps = [row[2]['park_frontage_overlap_at_rest'] for row in observations]
    if overlaps != [False, True]:
        raise ValueError('Away/beside original source measurement differs')
    for name in ('road.xodr', 'frontage-inventory.json', 'park-review.json', 'exception-review.json', 'overview.mkv'):
        if len({sha(row[3] / name) for row in observations}) != 1:
            raise ValueError('Fixed park frontage or exception source changed: ' + name)
    vehicles = [read(row[3] / 'vehicle-spec-review.json') for row in observations]
    for key in ('vehicle_class', 'vehicle_overall_length_m', 'vehicle_unladen_mass_kg'):
        if vehicles[0][key] != vehicles[1][key]:
            raise ValueError('Fixed commercial vehicle specification changed: ' + key)
    return {'format': 'c135709-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': True, 'differences_checked': True,
            'park_frontage_overlap_at_rest': overlaps,
            'analysis_sha256': {row[0]: row[4] for row in observations},
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--processing', action='append', required=True)
    parser.add_argument('--omit-case')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.comparison, args.processing, args.omit_case)
    if args.output.exists():
        raise ValueError('Retain previous comparison audit result')
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison}))


if __name__ == '__main__':
    main()

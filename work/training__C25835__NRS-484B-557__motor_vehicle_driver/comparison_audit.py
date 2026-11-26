"""Independent fixed-source and measured 15/50-foot rail-stop contrast audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED_SOURCES = ('road.xodr', 'rail-inventory.json',
    'designation-authority.txt', 'sign-authority.txt',
    'designation-review.json', 'sign-review.json', 'occluder-review.json')


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
        raise ValueError('Unknown rail-stop comparison')
    paths = dict(item.split('=', 1) for item in processing_specs)
    if set(paths) != set(comparison['case_ids']) or omit_case:
        raise ValueError('Missing comparison case: ' + str(omit_case or
                         sorted(set(comparison['case_ids']) - set(paths))))
    manifest = read(HERE / 'execution-manifest.json')
    observations = []
    for case in comparison['case_ids']:
        selected = next(row for row in manifest['cases'] if row['case_id'] == case)
        saved = read(paths[case])
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
                saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
                saved.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Selected rail comparison source differs')
        stage = Path(saved['analysis_directory'])
        config, report, result = (read(stage / name) for name in
                                  ('config.json', 'analysis-report.json', 'result.json'))
        if result.get('case_id') != case:
            raise ValueError('Rail comparison result identity differs')
        for item in report.get('measurements', {}).values():
            for name, digest in item.get('sources', {}).items():
                if digest != sha(stage / name):
                    raise ValueError('Rail comparison source changed: ' + name)
        value = result.get('measured_values', {})
        distances = value.get('stop_reference_distances_from_nearest_track_ft', {})
        if set(distances) != {'front_ft', 'center_ft', 'rear_ft'}:
            raise ValueError('Rail comparison lacks all vehicle reference distances')
        if not value.get('approach_observed') or not value.get('subsequent_proceeding_observed'):
            raise ValueError('Rail comparison lacks stop-to-proceed history')
        observations.append((case, config, value, stage, sha(stage / 'analysis-report.json')))
    configs = [row[1] for row in observations]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                  'cameras', 'required_atoms', 'source_packets', 'brake_gain'):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError('Rail comparison fixed condition changed: ' + field)
    for name in FIXED_SOURCES:
        if len({sha(row[3] / name) for row in observations}) != 1:
            raise ValueError('Rail comparison fixed source changed: ' + name)
    requests = [config['requested_stop_center_ft'] for config in configs]
    centers = [row[2]['stop_reference_distances_from_nearest_track_ft']['center_ft']
               for row in observations]
    if len(set(requests)) != len(requests) or len(set(centers)) != len(centers):
        raise ValueError('Rail comparison requested or observed positions collapsed')
    if any(abs(center - requested) > 1.0 for center, requested in zip(centers, requests)):
        raise ValueError('Rail comparison measured positions miss requests')
    if comparison_id.endswith('lower_boundary'):
        if sorted(requests) != [10, 15, 25]:
            raise ValueError('15-foot below/at/above sweep differs')
    elif comparison_id.endswith('upper_boundary'):
        if sorted(requests) != [25, 50, 50.5]:
            raise ValueError('50-foot below/at/above sweep differs')
    else:
        raise ValueError('Unrecognized boundary sweep')
    return {'format': 'c25835-independent-rail-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'requested_center_ft': requests, 'observed_center_ft': centers,
            'fixed_conditions_checked': True, 'differences_checked': True,
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

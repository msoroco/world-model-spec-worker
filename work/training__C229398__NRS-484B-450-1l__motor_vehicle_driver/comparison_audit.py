"""Independent exact-case clear versus highway-side double-parking audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(comparison_id, processing_specs, omit_case=None):
    plan = read(HERE / 'case-plan.json')
    comparison = next((row for row in plan['comparisons']
                       if row['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown exact comparison')
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
                saved.get('timestamp_joins', {}).get('frames') != 600 or
                saved.get('final_video_checks', {}).get('frames') != 600):
            raise ValueError('Selected comparison saved source differs')
        stage = Path(saved['analysis_directory'])
        config = read(stage / 'config.json')
        report = read(stage / 'analysis-report.json')
        place = report.get('measurements', {}).get('highway_side_place', {})
        if place.get('method') != 'place_observation':
            raise ValueError('Comparison lacks source-bound place measurement')
        for name, value in place.get('sources', {}).items():
            if digest(stage / name) != value:
                raise ValueError('Comparison source changed: ' + name)
        observations.append((case, config, place['value'], stage,
                             digest(stage / 'analysis-report.json')))
    configs = [row[1] for row in observations]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                  'cameras', 'required_atoms', 'source_packets'):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError('Comparison fixed condition changed: ' + field)
    overlaps = [row[2]['concurrent_overlap_at_rest_frame_count'] for row in observations]
    if overlaps[0] != 0 or overlaps[1] <= 0:
        raise ValueError('Clear/occupied original source measurement differs')
    for name in ('road.xodr', 'map-geometry.json'):
        if len({digest(row[3] / name) for row in observations}) != 1:
            raise ValueError('Fixed road or surveyed curb source changed: ' + name)
    return {'format': 'c229398-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': True, 'differences_checked': True,
            'concurrent_overlap_at_rest_frame_count': overlaps,
            'analysis_sha256': {row[0]: row[4] for row in observations},
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--processing', action='append', required=True)
    parser.add_argument('--omit-case')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.comparison, args.processing, args.omit_case)
    if args.output.exists():
        raise ValueError('Retain previous comparison audit result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison}))


if __name__ == '__main__':
    main()

"""Compare the two source-bound U-turn diagnostic measurements."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, specifications, omit_case):
    plan = read(HERE / 'case-plan.json')
    comparison = next((x for x in plan['comparisons'] if x['comparison_id'] == comparison_id), None)
    if comparison is None:
        raise ValueError('Unknown comparison')
    paths = dict(item.split('=', 1) for item in specifications)
    if set(paths) != set(comparison['case_ids']) or omit_case:
        missing = omit_case or sorted(set(comparison['case_ids']) - set(paths))
        raise ValueError('Missing comparison case: ' + str(missing))
    values = []
    for case in comparison['case_ids']:
        saved = read(paths[case])
        if (saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
                saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('originals_preserved') is not True or
                saved.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Selected comparison source differs')
        stage = Path(saved['analysis_directory'])
        config = read(stage / 'config.json')
        report = read(stage / 'analysis-report.json')
        motion = report.get('measurements', {}).get('school_zone_turn_observation', {})
        if (motion.get('method') != 'measure_school_turn' or
                any(sha(stage / name) != checksum for name, checksum in motion.get('sources', {}).items())):
            raise ValueError('Source-bound turn observation differs')
        for name in ('a_no_children', 'b_not_in_session', 'c_operation_interval',
                     'd_operational_beacon_class_hours', 'e_no_operational_beacon_sign'):
            item = report.get('measurements', {}).get('exception_' + name, {})
            if item.get('method') != 'measure_exception' or item.get('value', {}).get('legal_verdict') != 'unresolved':
                raise ValueError('Separate exception source review missing: ' + name)
        values.append((case, config, motion['value'], sha(stage / 'analysis-report.json')))
    first, second = values
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'source_packets'):
        if first[1][field] != second[1][field]:
            raise ValueError('Fixed comparison condition changed: ' + field)
    straight = first[2]['cumulative_absolute_heading_change_deg']
    turned = second[2]['cumulative_absolute_heading_change_deg']
    if not (straight < 30 and 150 <= turned <= 210):
        raise ValueError('Source-measured turn contrast unproven')
    return {'format': 'c263073-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': True, 'deliberate_turn_difference_checked': True,
            'observed_heading_change_deg': {first[0]: straight, second[0]: turned},
            'analysis_sha256': {item[0]: item[3] for item in values},
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
        raise ValueError('Retain previous comparison audit')
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison}))


if __name__ == '__main__':
    main()

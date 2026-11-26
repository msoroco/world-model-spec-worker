"""Compare source-bound U-turn and exact school-zone exception contexts."""
import argparse
import hashlib
import json
from pathlib import Path
from native.branch_cases import FACT_TOPICS, expected_facts

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
        context = read(stage / 'school-context.json')
        review = context['independent_review']
        facts = review['case_facts']
        suffix = case.rsplit('__', 1)[-1]
        expected = expected_facts(suffix)
        for key, topics in FACT_TOPICS.items():
            fact = facts.get(key, {})
            if fact.get('value') != expected[key] or fact.get('source_topics') != list(topics):
                raise ValueError('Selected comparison school fact differs: ' + key)
            if fact.get('source_sha256') != {topic: sha(stage / review['records'][topic]['path']) for topic in topics}:
                raise ValueError('Selected comparison school source hash differs: ' + key)
        definition = review.get('beacon_definition', {})
        definition_topics = ('beacon_configuration', 'beacon_lights', 'zone_sign')
        if (type(definition.get('yellow_light_count')) is not int or
                definition['yellow_light_count'] < 2 or
                definition.get('flashes_alternately') is not True or
                definition.get('used_with_sign') is not True or
                definition.get('source_topics') != list(definition_topics) or
                definition.get('source_sha256') !=
                {topic: sha(stage / review['records'][topic]['path']) for topic in definition_topics}):
            raise ValueError('Statutory beacon definition source differs')
        values.append((case, config, motion['value'], sha(stage / 'analysis-report.json'),
                       {key: facts[key]['value'] for key in FACT_TOPICS}))
    first, second = values
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'source_packets'):
        if first[1][field] != second[1][field]:
            raise ValueError('Fixed comparison condition changed: ' + field)
    first_heading = first[2]['cumulative_absolute_heading_change_deg']
    second_heading = second[2]['cumulative_absolute_heading_change_deg']
    if comparison_id.endswith('__comparison'):
        if not (first_heading < 30 and 150 <= second_heading <= 210):
            raise ValueError('Source-measured turn contrast unproven')
        changed = set()
    else:
        if not (150 <= first_heading <= 210 and 150 <= second_heading <= 210):
            raise ValueError('Fixed U-turn comparison changed')
        suffix = comparison_id.split('__')[-1].removesuffix('_comparison')
        changed = {
            'exception_a': {'children_present'},
            'exception_b': {'school_session_day', 'half_hour_operation_interval', 'class_hours'},
            'exception_c': {'half_hour_operation_interval', 'class_hours'},
            'exception_d': {'yellow_lights_flashing'},
            'exception_e': {'sign_limit_in_effect'},
        }[suffix]
        actual = {key for key in FACT_TOPICS if first[4][key] != second[4][key]}
        if actual != changed:
            raise ValueError('Controlled exception source contrast differs: ' + str(sorted(actual)))
    return {'format': 'c263073-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': True, 'deliberate_source_differences_checked': sorted(changed),
            'observed_heading_change_deg': {first[0]: first_heading, second[0]: second_heading},
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

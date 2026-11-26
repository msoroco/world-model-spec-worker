"""Independent held-conditions and measured entry-location contrast audit."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXED_SOURCES = ('road.xodr', 'access-authority.txt', 'device-authority.txt',
    'device-content.txt', 'device-erection.txt', 'entrance-extent.txt',
    'highway-dedication.txt', 'public-use.txt', 'jurisdiction.txt',
    'vehicle-eligibility.txt')


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
        raise ValueError('Unknown entry comparison')
    paths = dict(item.split('=', 1) for item in processing_specs)
    if set(paths) != set(comparison['case_ids']) or omit_case:
        raise ValueError('Missing comparison case: ' + str(omit_case or sorted(set(comparison['case_ids'])-set(paths))))
    manifest = read(HERE / 'execution-manifest.json')
    observations = []
    for case in comparison['case_ids']:
        selected = next(row for row in manifest['cases'] if row['case_id'] == case)
        saved = read(paths[case])
        if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
                saved.get('case_id') != case or saved.get('candidate_id') != 'primary' or
                saved.get('native_revision', {}).get('construction_sha256') != selected['construction_sha256'] or
                saved.get('timestamp_joins', {}).get('frames') != 600):
            raise ValueError('Selected entry comparison source differs')
        stage = Path(saved['analysis_directory'])
        config, report, result = (read(stage / name) for name in
                                  ('config.json', 'analysis-report.json', 'result.json'))
        if result.get('case_id') != case:
            raise ValueError('Entry comparison result identity differs')
        for item in report.get('measurements', {}).values():
            for name, digest in item.get('sources', {}).items():
                if digest != sha(stage / name):
                    raise ValueError('Entry comparison source changed: ' + name)
        value = result.get('measured_values', {})
        if len(value.get('entry_events', [])) != 1:
            raise ValueError('Entry comparison lacks original body event')
        observations.append((case, config, value, stage, sha(stage / 'analysis-report.json')))
    configs = [row[1] for row in observations]
    for field in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s', 'cameras',
                  'required_atoms', 'source_packets', 'steer_gain'):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError('Entry comparison fixed condition changed: ' + field)
    for name in FIXED_SOURCES:
        if len({sha(row[3] / name) for row in observations}) != 1:
            raise ValueError('Entry comparison fixed source changed: ' + name)
    inventories = [read(row[3] / 'access-inventory.json') for row in observations]
    for key in ('road_survey', 'highway_road_id_candidate', 'frontage_road_id_candidate',
                'paved_entry_road_id_candidate', 'device_actor_id', 'device_blueprint_id'):
        if any(item[key] != inventories[0][key] for item in inventories[1:]):
            raise ValueError('Entry comparison fixed Native inventory changed: ' + key)
    if [config['entry_mode'] for config in configs] != ['witness_1', 'witness_2']:
        raise ValueError('Selected entry modes differ')
    events = [row[2]['entry_events'][0] for row in observations]
    if ([event['within_indicated_entrance'] for event in events] != [True, False] or
            abs(events[1]['measured_center_x_m']-events[0]['measured_center_x_m']-60) > .1):
        raise ValueError('Measured indicated/outside entry contrast differs')
    return {'format': 'c228131-independent-entry-comparison-audit-v1',
            'comparison_id': comparison_id, 'case_ids': comparison['case_ids'],
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

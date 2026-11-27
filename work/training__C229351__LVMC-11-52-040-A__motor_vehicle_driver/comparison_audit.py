"""Independent seven-pair roadway-rest comparison audit and CPU isolation test."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(HERE / 'native')]
from selected_plan import CASES, request, compare
from source_audit import extract, comparison_audit, road_edge_context
from parking_measure import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def selftest(comparison_id, negative=False):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    pair = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison_id), None)
    if pair is None or len(pair['case_ids']) != 2 or not pair['fixed_conditions'] or not pair['deliberate_differences']:
        raise ValueError('Missing exact controlled comparison')
    surveys = {}
    for index, case in enumerate(CASES):
        fixture = json.loads((HERE / 'native' / f'fixture-{index}.json').read_text())
        surveys[case] = json.loads(fixture['files']['road_edge_survey.json'])
    if negative:
        surveys[pair['case_ids'][1]]['roadway_boundary_source_id'] = 'another-road-edge'
        compare({case: request(case, survey, allow_fixture=True)
                 for case, survey in surveys.items()})
        raise AssertionError('Changed comparison road edge accepted')
    report = compare({case: request(case, survey, allow_fixture=True)
                      for case, survey in surveys.items()})
    if len(report['case_ids']) != 6:
        raise ValueError('Incomplete diagnostic comparison family')
    return {'comparison_id': comparison_id, 'case_ids': pair['case_ids'],
            'fixed_conditions_checked': pair['fixed_conditions'],
            'deliberate_differences_checked': pair['deliberate_differences'],
            'scope': 'synthetic source isolation; original Native comparison pending'}


def audit(comparison_id, sources_json, output):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    pair = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison_id), None)
    if pair is None:
        raise ValueError('Unknown exact controlled comparison')
    roots = {case: Path(path).resolve() for case, path in json.loads(Path(sources_json).read_text()).items()}
    if set(roots) != set(CASES):
        raise ValueError('All six exact original sources required for comparison isolation')
    extracts, surveys, observed, source_hashes = {}, {}, {}, {}
    for case, root in roots.items():
        result = json.loads((root / 'result.json').read_text())
        if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is not False:
            raise ValueError('Original Native comparison source required: ' + case)
        paths = {name: root / filename for name, filename in
                 [('samples', 'native_samples.jsonl'), ('frames', 'video_frames.jsonl'),
                  ('geometry', 'road_geometry.json'), ('survey', 'road_edge_survey.json')]}
        if not all(path.is_file() for path in paths.values()):
            raise ValueError('Missing original comparison source: ' + case)
        surveys[case] = json.loads(paths['survey'].read_text())
        extracts[case] = extract(case, paths['samples'], paths['frames'],
                                 paths['geometry'], paths['survey'])
        observed[case] = measure(extracts[case], road_edge_context(paths['geometry']))
        source_hashes[case] = {name: sha(path) for name, path in paths.items()}
    full = comparison_audit(extracts, surveys, observed)
    report = next((row for row in full['comparisons']
                   if row['case_ids'] == pair['case_ids']), None)
    if report is None:
        raise ValueError('Measured comparison pair absent')
    result = {'format': 'worker-roadside-original-comparison-audit',
              'comparison_id': comparison_id, 'case_ids': pair['case_ids'],
              'source_hashes': source_hashes, 'fixed_conditions': pair['fixed_conditions'],
              'deliberate_differences': pair['deliberate_differences'],
              'measured_pair': report, 'legal_result': None,
              'actual_activity_review_required': True}
    output = Path(output).resolve()
    if ROOT / 'state/operations/worker_exchange' not in output.parents:
        raise ValueError('Independent comparison output belongs in local operations')
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--negative', action='store_true')
    parser.add_argument('--sources-json')
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(selftest(args.comparison, args.negative) if args.self_test else
        audit(args.comparison, args.sources_json, args.output)))

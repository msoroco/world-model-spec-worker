"""Check original taxi route source equality and first-turn contrast."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(comparison, bindings):
    plan = json.loads((HERE / 'case-plan.json').read_text())
    spec = next((row for row in plan['comparisons'] if row['comparison_id'] == comparison), None)
    if spec is None:
        raise ValueError('Unknown comparison')
    if set(bindings) != set(spec['case_ids']):
        raise ValueError('Missing comparison case')
    facts = {}
    for case in spec['case_ids']:
        saved_path = bindings[case]
        saved = json.loads(saved_path.read_text())
        if (saved.get('case_id') != case or saved.get('recorded_only') is not True or
                saved.get('passed') is not True or saved.get('timestamp_joins', {}).get('frames') != 600 or
                saved.get('final_video_checks', {}).get('frames') != 600):
            raise ValueError('Incomplete saved case')
        stage = Path(saved['analysis_directory'])
        result = json.loads((stage / 'result.json').read_text())
        config = json.loads((stage / 'config.json').read_text())
        analysis = json.loads((stage / 'analysis-report.json').read_text())
        measurement = analysis['measurements']['source_bound_first_turn']
        value = measurement['value']
        if (result['case_id'] != case or len((stage / 'trace.jsonl').read_text().splitlines()) != 600 or
                len((stage / 'video_frames.jsonl').read_text().splitlines()) != 600 or
                value['observed_first_turn'] != value['requested_first_turn']):
            raise ValueError('Source-bound first turn differs')
        facts[case] = {'road_sha256': sha(stage / 'road.xodr'),
            'survey_sha256': sha(stage / 'route-survey.json'),
            'rate_hz': config['rate_hz'], 'duration_s': config['duration_s'],
            'camera_profile': [(camera['name'], camera['width'], camera['height'], camera['fov_deg'])
                               for camera in config['cameras']],
            'observed_first_turn': value['observed_first_turn'],
            'sampled_path_m': value['sampled_path_m'],
            'processing_sha256': sha(saved_path)}
    left, right = [facts[case] for case in spec['case_ids']]
    for key in ('road_sha256', 'survey_sha256', 'rate_hz', 'duration_s', 'camera_profile'):
        if left[key] != right[key]:
            raise ValueError('Comparison fixed condition differs: ' + key)
    if [left['observed_first_turn'], right['observed_first_turn']] != ['right', 'straight']:
        raise ValueError('Comparison first-turn contrast differs')
    if min(left['sampled_path_m'], right['sampled_path_m']) < 100:
        raise ValueError('Comparison route sampling incomplete')
    return {'format': 'c110875-independent-comparison-v1', 'comparison_id': comparison,
        'cases': facts, 'diagnostic_only': True, 'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--processing', action='append', default=[])
    parser.add_argument('--omit-case')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    bindings = {}
    for token in args.processing:
        case, path = token.split('=', 1)
        if case != args.omit_case:
            bindings[case] = Path(path)
    receipt = review(args.comparison, bindings)
    if args.output.exists():
        raise ValueError('Retain previous comparison result')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_id': args.comparison}))


if __name__ == '__main__':
    main()

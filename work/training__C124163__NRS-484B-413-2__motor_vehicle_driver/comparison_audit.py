"""Independent saved-source distance comparisons; no legal or physical verdict."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(first, second):
    roots = [Path(first), Path(second)]
    configs = [json.loads((root/'config.json').read_text()) for root in roots]
    reports = [json.loads((root/'analysis-report.json').read_text()) for root in roots]
    fixed = ('law_id', 'cell_id', 'actor', 'duration_s', 'rate_hz',
             'cameras', 'district_class', 'weather', 'layout', 'maneuver')
    for key in fixed:
        if configs[0][key] != configs[1][key]:
            raise ValueError('Comparison fixed condition differs: '+key)
    left, right = [x['requested_signal_distance_m'] for x in configs]
    if left <= right:
        raise ValueError('Signal distance request order differs')
    measured = [r['measurements']['continuous_signal_distance']['value']
                ['continuous_native_light_state_distance_m'] for r in reports]
    if measured[0] <= measured[1]:
        raise ValueError('Synthetic source distance order differs')
    threshold = 91.44 if configs[0]['district_class'] == 'other_area' else 30.48
    return {'format': 'c124163-independent-comparison-audit-v1',
            'case_ids': [cfg['case_id'] for cfg in configs],
            'fixed_conditions': list(fixed),
            'deliberate_difference': 'requested_signal_distance_m',
            'requested_distance_m': [left, right],
            'diagnostic_native_light_state_distance_m': measured,
            'statutory_distance_m': threshold,
            'source_hashes': {'first': sha(roots[0]/'signal-source.jsonl'),
                              'second': sha(roots[1]/'signal-source.jsonl')},
            'diagnostic_fixture': True, 'original_native_observed': False,
            'visible_signal_pixels_reviewed': False,
            'district_weather_originally_verified': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ('first', 'second', 'output'):
        parser.add_argument('--'+key, required=True)
    args = parser.parse_args()
    result = audit(args.first, args.second)
    Path(args.output).write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'case_ids': result['case_ids'],
                      'diagnostic_native_light_state_distance_m':
                      result['diagnostic_native_light_state_distance_m']}))

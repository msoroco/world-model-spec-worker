"""Independent controlled speed-request and saved-speed comparison."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(first, second, third):
    roots = [Path(first), Path(second), Path(third)]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in roots]
    for key in ('law_id', 'cell_id', 'actor', 'duration_s', 'rate_hz', 'cameras'):
        if any(configs[0][key] != item[key] for item in configs[1:]):
            raise ValueError('Comparison fixed condition differs: ' + key)
    if [item['requested_speed_mph'] for item in configs] != [53, 55, 57]:
        raise ValueError('Comparison request delta differs')
    measured = [report['measurements']['school_bus_speed_0']['value']['maximum_observed_mph'] for report in reports]
    if measured[0] >= 55 or abs(measured[1] - 55) > .05 or measured[2] <= 55:
        raise ValueError('Diagnostic observed speed does not straddle 55 mph')
    reviews = [json.loads((root / 'passenger_trip_review.json').read_text()) for root in roots]
    for review in reviews:
        if (review.get('judged_driver_actor_id') != review.get('bus_driver_actor_id') or
                not review.get('driver_bus_join_source') or
                review.get('trip_purpose') != 'transporting pupils to or from school'):
            raise ValueError('Comparison bus driver or school-trip source differs')
    return {'format': 'c230281-independent-comparison-audit-v1',
            'case_ids': [config['case_id'] for config in configs],
            'fixed_conditions': ['law_id', 'cell_id', 'actor',
                                 'duration_s', 'rate_hz', 'cameras'],
            'deliberate_difference': 'requested_speed_mph',
            'requested_speed_mph': [53, 55, 57], 'diagnostic_observed_mph': measured,
            'source_hashes': {str(speed): sha(root / 'bus_motion.jsonl')
                              for speed, root in zip((53, 55, 57), roots)},
            'diagnostic_fixture': True, 'original_native_observed': False,
            'school_trip_legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--third', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.first, args.second, args.third)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'requested_speed_mph': result['requested_speed_mph'],
                      'diagnostic_observed_mph': result['diagnostic_observed_mph']}))

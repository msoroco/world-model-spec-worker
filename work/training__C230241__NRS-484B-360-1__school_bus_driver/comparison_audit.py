"""Independent controlled speed-request and saved-speed comparison."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(first, second):
    roots = [Path(first), Path(second)]
    configs = [json.loads((root / 'config.json').read_text()) for root in roots]
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in roots]
    for key in ('law_id', 'cell_id', 'actor', 'cell_control', 'duration_s', 'rate_hz', 'cameras'):
        if configs[0][key] != configs[1][key]:
            raise ValueError('Comparison fixed condition differs: ' + key)
    if configs[0]['requested_speed_mph'] != 52 or configs[1]['requested_speed_mph'] != 58:
        raise ValueError('Comparison request delta differs')
    measured = [report['measurements']['school_bus_speed']['value']['maximum_observed_mph'] for report in reports]
    if measured[0] >= 55 or measured[1] <= 55:
        raise ValueError('Diagnostic observed speed does not straddle 55 mph')
    return {'format': 'c230241-independent-comparison-audit-v1',
            'case_ids': [config['case_id'] for config in configs],
            'fixed_conditions': ['law_id', 'cell_id', 'actor', 'cell_control',
                                 'duration_s', 'rate_hz', 'cameras'],
            'deliberate_difference': 'requested_speed_mph',
            'requested_speed_mph': [52, 58], 'diagnostic_observed_mph': measured,
            'source_hashes': {'probe_a': sha(roots[0] / 'bus_motion.jsonl'),
                              'probe_b': sha(roots[1] / 'bus_motion.jsonl')},
            'diagnostic_fixture': True, 'original_native_observed': False,
            'school_trip_legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--first', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.first, args.second)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'requested_speed_mph': result['requested_speed_mph'],
                      'diagnostic_observed_mph': result['diagnostic_observed_mph']}))

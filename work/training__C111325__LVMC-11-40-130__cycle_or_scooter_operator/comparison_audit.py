"""Independent paired speed contrast audit from saved original-source rows."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(root, case):
    root = Path(root)
    config_path = root / 'config.json'
    trace_path = root / 'native-bicycle-trace.jsonl'
    context_path = root / 'context.json'
    config = json.loads(config_path.read_text())
    context = json.loads(context_path.read_text())
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    if config['case_id'] != case or len(rows) != 600 or any(row['sample_index'] != i for i, row in enumerate(rows)):
        raise ValueError('Incomplete or wrong exact comparison source')
    if any(row['source_kind'] != context['source_kind'] for row in rows):
        raise ValueError('Comparison provenance changed')
    speeds = [sum(v*v for v in row['velocity_xy_mps'])**0.5 for row in rows]
    return {'case_id': case, 'requested_speed_mps': config['requested_speed_mps'],
            'observed_peak_speed_mps': max(speeds),
            'fixed_conditions_id': context['fixed_conditions_id'],
            'source_kind': context['source_kind'],
            'source_hashes': {'config.json': sha(config_path),
                              'native-bicycle-trace.jsonl': sha(trace_path),
                              'context.json': sha(context_path)}}


def audit(root_a, root_b, case_a, case_b, comparison_id):
    a = source(root_a, case_a)
    b = source(root_b, case_b)
    if a['fixed_conditions_id'] != b['fixed_conditions_id']:
        raise ValueError('Comparison fixed conditions differ')
    if not a['requested_speed_mps'] < b['requested_speed_mps'] or not a['observed_peak_speed_mps'] < b['observed_peak_speed_mps']:
        raise ValueError('Selected measured speed contrast absent')
    return {'format': 'c111325-independent-comparison-audit-v1',
            'comparison_id': comparison_id, 'cases': [a, b],
            'deliberate_difference': 'bicycle_approach_speed',
            'requested_delta_mps': b['requested_speed_mps'] - a['requested_speed_mps'],
            'observed_peak_delta_mps': b['observed_peak_speed_mps'] - a['observed_peak_speed_mps'],
            'diagnostic_fixture': a['source_kind'] == b['source_kind'] == 'synthetic_native_mock',
            'physical_acceptance': False, 'legal_prudence_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    for key in ('root-a', 'root-b', 'case-a', 'case-b', 'comparison', 'output'):
        parser.add_argument('--' + key, required=True)
    args = parser.parse_args()
    report = audit(args.root_a, args.root_b, args.case_a, args.case_b, args.comparison)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison_id': report['comparison_id'],
                      'observed_peak_delta_mps': report['observed_peak_delta_mps'],
                      'physical_acceptance': False}))


if __name__ == '__main__':
    main()

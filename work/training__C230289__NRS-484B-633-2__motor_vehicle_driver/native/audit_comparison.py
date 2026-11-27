"""Independent selected-case source isolation for structural speed pair."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def audit(low, high, tamper_sign=False):
    low, high = Path(low), Path(high)
    first = json.loads((low / 'original_bridge_survey.json').read_text())
    second = json.loads((high / 'original_bridge_survey.json').read_text())
    if tamper_sign:
        second['signs'][0]['source_id'] = 'changed-source-in-negative-test'
    if first != second:
        raise ValueError('Bridge, DOT authority, sign or route fixed source changed')
    configurations = [json.loads((path / 'config.json').read_text()) for path in (low, high)]
    one, two = configurations
    fixed = set(one) - {'case_id', 'selected_case_id', 'requested_offset_from_declared_maximum_mph'}
    if set(one) != set(two) or any(one[key] != two[key] for key in fixed):
        raise ValueError('Fixed Native configuration changed')
    if (one['requested_offset_from_declared_maximum_mph'], two['requested_offset_from_declared_maximum_mph']) != (-10, 10):
        raise ValueError('Declared controller contrast changed')
    findings = [json.loads((path / 'bridge-findings.json').read_text()) for path in (low, high)]
    a, b = findings
    maximum = first['administrative_declaration']['safe_maximum_mph']
    if a['declared_maximum_mph'] != maximum or b['declared_maximum_mph'] != maximum:
        raise ValueError('Measured contrast changed DOT source maximum')
    if not (a['max_observed_structure_speed_mph'] < maximum < b['max_observed_structure_speed_mph']):
        raise ValueError('Observed speed did not distinguish structural maximum')
    if a['structure_frames_above_declared_maximum'] or not b['structure_frames_above_declared_maximum']:
        raise ValueError('Structure crossing speed observation missing')
    trace_a, trace_b = (rows(path / 'bridge-native.jsonl') for path in (low, high))
    if len(trace_a) != 600 or len(trace_b) != 600:
        raise ValueError('Duration differs')
    if {row['vehicle_id'] for row in trace_a} != {row['vehicle_id'] for row in trace_b}:
        raise ValueError('Original actor identity differs')
    for path, finding, trace in ((low, a, trace_a), (high, b, trace_b)):
        if finding['original_bridge_survey_sha256'] != sha(path / 'original_bridge_survey.json'):
            raise ValueError('Finding detached from survey')
        if finding['original_native_trace_sha256'] != sha(path / 'bridge-native.jsonl'):
            raise ValueError('Finding detached from measured speed')
        if not any(row['on_structure_verified'] for row in trace):
            raise ValueError('No surveyed structure crossing')
    return {'comparison_id': 'bridge_declared_maximum_speed', 'fixed_survey_sha256': sha(low / 'original_bridge_survey.json'),
            'requested_offsets_mph': [-10, 10], 'measured_structure_speeds_mph': [a['max_observed_structure_speed_mph'], b['max_observed_structure_speed_mph']],
            'source_difference': 'controller request only; occupancy timing is a measured consequence',
            'synthetic_cpu_diagnostic_only': True, 'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--low', required=True)
    parser.add_argument('--high', required=True)
    parser.add_argument('--tamper-sign', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.low, args.high, args.tamper_sign), sort_keys=True))

"""Independent original-source comparison for the bridge versus ground pair."""
import argparse
import hashlib
import json
from pathlib import Path

from bridge_measure import measure


def _read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + path.name)
    data = path.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def _case(root):
    root = Path(root)
    config_data, config_hash = _read(root / 'config.json')
    trace_data, trace_hash = _read(root / 'bridge-trace.jsonl')
    bridge_data, bridge_hash = _read(root / 'bridge-map.json')
    map_data, map_hash = _read(root / 'video_frames.jsonl')
    config = json.loads(config_data)
    measured = measure(trace_data, bridge_data,
                       trace_sha256=trace_hash, bridge_sha256=bridge_hash)
    mapping = [json.loads(line) for line in map_data.splitlines() if line.strip()]
    if len(measured['rows']) != len(mapping) or len(mapping) != 600:
        raise ValueError('Comparison lacks full original frame join')
    stationary = [r for r in measured['rows'] if r['stationary_candidate']]
    if not stationary:
        raise ValueError('Comparison lacks observed stationary interval')
    return {'config': config, 'bridge_hash': bridge_hash,
            'trace_hash': trace_hash, 'config_hash': config_hash,
            'map_hash': map_hash, 'stationary': stationary,
            'bridge_relations': sorted(set(r['bridge_relation'] for r in stationary))}


def audit(false_attempt, true_attempt):
    ground = _case(false_attempt)
    bridge = _case(true_attempt)
    a, b = ground['config'], bridge['config']
    if a['case_id'].rsplit('__', 1)[-1] != 'false' or b['case_id'].rsplit('__', 1)[-1] != 'true':
        raise ValueError('Comparison case identities differ')
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                'cameras', 'required_atoms', 'source_packets',
                'requested_halt_cause'):
        if a.get(key) != b.get(key):
            raise ValueError('Comparison fixed condition changed: ' + key)
    if ground['bridge_hash'] != bridge['bridge_hash']:
        raise ValueError('Comparison bridge geometry changed')
    if a.get('requested_stationary_footprint_on_bridge') is not False or \
            b.get('requested_stationary_footprint_on_bridge') is not True:
        raise ValueError('Comparison requested variable changed')
    if ground['bridge_relations'] != ['none'] or bridge['bridge_relations'] != ['full']:
        raise ValueError('Comparison observed bridge relation not isolated')
    return {'format': 'c31675-original-bridge-comparison-v1', 'passed': True,
            'fixed_conditions': ['law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                                 'cameras', 'required_atoms', 'source_packets',
                                 'requested_halt_cause', 'bridge-map.json'],
            'deliberate_difference': 'stationary_footprint_on_bridge',
            'observed': {'ground': ground['bridge_relations'],
                         'bridge': bridge['bridge_relations']},
            'source_hashes': {'ground_trace': ground['trace_hash'],
                              'bridge_trace': bridge['trace_hash'],
                              'shared_bridge_map': bridge['bridge_hash']},
            'physical_acceptance_claimed': False, 'legal_result': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--false-attempt', required=True)
    parser.add_argument('--true-attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.false_attempt, args.true_attempt)))

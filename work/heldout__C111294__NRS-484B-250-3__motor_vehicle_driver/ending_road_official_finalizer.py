"""Saved-only official-device observation joined to the ending-road trace."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from ending_road_finalizer import (analyze as analyze_intersection,
                                   build_result as build_intersection_result,
                                   measure_intersection as base_measure_intersection)
from ending_road_runner import CASE
from official_geometry_source_audit import audit as audit_official_geometry


def measure_intersection(topology_path, participant_path):
    return base_measure_intersection(topology_path, participant_path)


def _required(root, name):
    path = root / name
    if not path.is_file() or not path.read_bytes():
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def measure_official_device(context_path, states_path, topology_path, map_path):
    context = json.loads(context_path.read_text())
    topology = json.loads(topology_path.read_text())
    mapping = [json.loads(line) for line in map_path.read_text().splitlines()]
    states = [json.loads(line) for line in states_path.read_text().splitlines()]
    if not states or len(states) != len(mapping):
        raise ValueError('Official-device original readback/frame-map length differs')
    subject = topology['lanes'][topology['subject_approach_lane']]
    if (str(context.get('junction_id')) != str(topology.get('junction_id')) or
            context.get('affected_road_id') != subject.get('road_id') or
            context.get('affected_lane_id') != subject.get('lane_id') or
            not context.get('opendrive_signal_id')):
        raise ValueError('Official device does not govern the selected ending approach')
    for video, row in zip(mapping, states):
        if ((row.get('frame'), row.get('time_s')) !=
                (video.get('carla_frame'), video.get('time_s')) or
                row.get('device_id') != context.get('device_id') or
                row.get('value') != row.get('native_state') or
                not row.get('native_state')):
            raise ValueError('Official-device original state join failed')
    return {'device_id': context['device_id'],
            'opendrive_signal_id': context['opendrive_signal_id'],
            'states_observed': sorted({row['native_state'] for row in states}),
            'frames': len(states), 'subsection_4_applicability': None,
            'official_legal_status_claimed': False}


def analyze(attempt):
    root = Path(attempt)
    report = analyze_intersection(root)
    geometry = audit_official_geometry(root)
    context, context_sha = _required(root, 'official_device_context.json')
    states, states_sha = _required(root, 'official_device_states.jsonl')
    topology, topology_sha = _required(root, 'intersection_topology.json')
    mapping, mapping_sha = _required(root, 'video_frames.jsonl')
    report['measurements']['official_device_observation'] = {
        'method': 'measure_official_device',
        'value': measure_official_device(context, states, topology, mapping),
        'sources': {'official_device_context.json': context_sha,
                    'official_device_states.jsonl': states_sha,
                    'intersection_topology.json': topology_sha,
                    'video_frames.jsonl': mapping_sha,
                    'official_geometry_binding.json': sha256((root / 'official_geometry_binding.json').read_bytes()).hexdigest(),
                    'road.xodr': sha256((root / 'road.xodr').read_bytes()).hexdigest()}}
    report['measurements']['official_geometry_source_audit'] = geometry
    report['limitations'].append('Native signal association and state do not establish legal official status or resolve subsection 4.')
    return report


def build_result(attempt, report):
    root = Path(attempt)
    result = build_intersection_result(root, report)
    value = report['measurements']['official_device_observation']['value']
    result['measured_values']['official_device_observation'] = value
    result['target_checks'].append({
        'target': 'selected ending approach has Native governing device',
        'requested': True, 'measured': bool(value['opendrive_signal_id']),
        'method': 'original affected-lane/junction association and per-frame state readback',
        'tolerance': None, 'matched': False,
        'physical_cause_confirmed': False,
        'cause_evidence': 'Original Native source; physical and legal review pending'})
    for name, unit, source in (
            ('official_device_state', 'categorical', 'official_device_states.jsonl'),
            ('device_id', 'native id', 'official_device_context.json')):
        result['recording_evidence'].append({
            'name': name, 'unit': unit, 'reference': source,
            'sha256': sha256((root / source).read_bytes()).hexdigest()})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior official-device analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == '__main__':
    main()

"""Saved-only source-bound lane and intersection observation finalizer."""
import argparse
import hashlib
import json
from pathlib import Path

from turn_lane_observations import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def source_sealed_turn_lane_measurement(value):
    return value


def analyze(attempt):
    root = Path(attempt).resolve()
    config = json.loads(source(root, 'config.json').read_text())
    case = config['selected_case_id']
    context_path = source(root, 'context.json')
    source_trace = source(root, 'original-trace.jsonl')
    receipt_path = source(root, 'receipt.json')
    receipt = json.loads(receipt_path.read_text())
    diagnostic = receipt.get('diagnostic_fixture') is True
    if receipt.get('assignment_id') != config['assignment_id'] or receipt.get('case_id') != case:
        raise ValueError('exact source receipt identity differs')
    if receipt.get('source_kind') != ('synthetic_diagnostic_fixture' if diagnostic else 'original_native_capture'):
        raise ValueError('original/diagnostic source kind differs')
    if receipt.get('context_sha256') != sha(context_path) or receipt.get('trace_sha256') != sha(source_trace):
        raise ValueError('source-sealed context or trace changed')
    context = json.loads(context_path.read_text())
    rows = [json.loads(line) for line in source_trace.read_text().splitlines()]
    if not rows or len(rows) != receipt.get('frame_count') or receipt.get('fps') != 20:
        raise ValueError('source frame count or rate differs')
    for index, row in enumerate(rows):
        if row.get('frame') != index or abs(row.get('time_s', -1) - index / 20) > .002:
            raise ValueError('source frame/time join differs')
    if not diagnostic:
        observations = measure(case, context_path, source_trace, receipt_path)
    else:
        if context.get('case_id') != case or context.get('independent_route_intent') != config['case']['route_request']:
            raise ValueError('diagnostic source-shaped case differs')
        observations = {'case_id': case, 'diagnostic_fixture': True,
                        'observations': rows, 'travel_through_judgment': 'unresolved',
                        'exclusive_turn_lane_judgment': 'unresolved', 'physical_acceptance': 'unverified'}
    values = {
        'public_highway_and_lane_design': {'lane_design': context['lane_design'], 'source': context['public_highway_source']},
        'right_turn_lane_occupancy': {'right_turn_lane_id': context['right_turn_lane_id'],
                                       'sampled_lane_ids': [row['lane_id'] for row in rows]},
        'intersection_traversal': {'entry_station_m': context['intersection_entry_station_m'],
                                   'exit_station_m': context['intersection_exit_station_m'],
                                   'sampled_stations_m': [row['ego_station_m'] for row in rows],
                                   'legal_judgment': 'unresolved'}}
    sources = {'context.json': sha(context_path), 'original-trace.jsonl': sha(source_trace),
               'receipt.json': sha(receipt_path)}
    measurements = {name: {'method': 'source_sealed_turn_lane_measurement',
                           'value': source_sealed_turn_lane_measurement(value), 'sources': sources}
                    for name, value in values.items()}
    evidence = []
    for channel in config['case']['recording_description']['channels']:
        name = channel['name']
        output = root / ('channel-' + name + '.jsonl')
        if output.exists():
            raise ValueError('retain prior derived channel')
        output.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': row.get('ego_station_m')
                                              if name == 'original_lane_and_vehicle_motion' else values}, sort_keys=True) + '\n'
                                  for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': output.name})
    channel = root / 'channel-reviewed_highway_and_turn_lane_site.json'
    channel.write_text(json.dumps({'reviewed_highway_and_turn_lane_site': {'map_sha256': context['map_sha256'], 'source': context['public_highway_source']}}) + '\n')
    evidence.append({'name': 'reviewed_highway_and_turn_lane_site', 'unit': 'source record', 'reference': channel.name})
    target = {'target': 'source-bound lane and intersection observation', 'requested': config['case']['route_request'],
              'measured': observations['travel_through_judgment'], 'method': 'original source-sealed Native trace',
              'tolerance': 0, 'matched': False, 'physical_cause_confirmed': False, 'cause_evidence': sources}
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case, 'measured_values': values, 'target_checks': [target],
              'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'original physical and site review pending',
              'physical_failure_flags': ['physical_acceptance_unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case, 'analysis_complete': True,
            'diagnostic_fixture': diagnostic, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False, 'measurements': measurements,
            'physical_checks': result['physical_checks'], 'realized_observables': result['realized_observables'],
            'limitations': ['Original public-highway and exclusive lane design review remains required.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')

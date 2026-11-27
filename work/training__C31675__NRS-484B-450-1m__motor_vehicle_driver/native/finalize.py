"""Saved-only bridge-body measurement; no legal or physical acceptance inference."""
import argparse
import hashlib
import json
from pathlib import Path

from bridge_measure import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def source(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    data = path.read_bytes()
    return data, hashlib.sha256(data).hexdigest()


def place_observation(rows):
    stationary = [r for r in rows if r['stationary_candidate']]
    return {'stationary_samples': len(stationary),
            'full_bridge_samples': sum(r['bridge_relation'] == 'full' for r in stationary),
            'outside_bridge_samples': sum(r['bridge_relation'] == 'none' for r in stationary),
            'partial_overlap_samples': sum(r['bridge_relation'] == 'partial' for r in stationary)}


def exception_observation(trace):
    return {'observed_other_actor_ids': sorted({r.get('other_actor_id') for r in trace
                                                if type(r.get('other_actor_id')) is int}),
            'requested_halt_causes': sorted({r.get('requested_halt_cause') for r in trace
                                             if r.get('requested_halt_cause')}),
            'traffic_conflict_necessity_verified': False,
            'law_police_device_direction_verified': False}


def bridge_scope_observation(rows):
    return {'relations_at_rest': sorted({r['bridge_relation'] for r in rows
                                         if r['stationary_candidate']}),
            'observed_frame_count': len(rows)}


def finalize(attempt_dir, output_path):
    attempt = Path(attempt_dir)
    config_data, config_hash = source(attempt / 'config.json')
    config = json.loads(config_data)
    trace_data, trace_hash = source(attempt / 'bridge-trace.jsonl')
    map_data, map_hash = source(attempt / 'bridge-map.json')
    mapping_data, mapping_hash = source(attempt / 'video_frames.jsonl')
    _, road_hash = source(attempt / 'road.xodr')
    for camera in CAMERAS:
        video = attempt / (camera + '.mkv')
        if not video.is_file() or video.stat().st_size == 0:
            raise ValueError('Missing required source: ' + video.name)
    if config['case_id'].rsplit('__', 1)[-1] not in ('false', 'true'):
        raise ValueError('unknown exact bridge case')
    geometry = json.loads(map_data)
    if geometry.get('source_kind') != 'native_bridge_lane_survey' or len(geometry.get('native_lane_survey', [])) != 6:
        raise ValueError('Missing original Native bridge survey')
    measurement = measure(trace_data, map_data, trace_sha256=trace_hash,
                          bridge_sha256=map_hash)
    rows = measurement['rows']
    mapping = [json.loads(line) for line in mapping_data.splitlines() if line.strip()]
    trace = [json.loads(line) for line in trace_data.splitlines() if line.strip()]
    if len(rows) != 600 or len(mapping) != 600:
        raise ValueError('incomplete original 600-frame bridge history')
    for index, (entry, frame) in enumerate(zip(trace, mapping)):
        if entry.get('native_frame') != frame.get('native_frame') or frame.get('video_frame') != index:
            raise ValueError('Native trace/video frame join differs')
        if abs(entry['time_s'] - frame['time_s']) > 1e-4:
            raise ValueError('Native trace/video timestamp join differs')
        if set(frame.get('camera_native_frames', {})) != set(CAMERAS) or any(
                frame['camera_native_frames'][c] != frame['native_frame'] for c in CAMERAS):
            raise ValueError('four original camera frames do not join')
    stationary = [row for row in rows if row['stationary_candidate']]
    if not stationary:
        raise ValueError('No observed stationary candidate interval')
    wanted = bool(config['requested_stationary_footprint_on_bridge'])
    full_at_rest = any(row['bridge_relation'] == 'full' for row in stationary)
    no_bridge_at_rest = all(row['bridge_relation'] == 'none' for row in stationary)
    matched = full_at_rest if wanted else no_bridge_at_rest
    evidence = {'source_hashes': {'config.json': config_hash,
        'bridge-trace.jsonl': trace_hash, 'bridge-map.json': map_hash,
        'video_frames.jsonl': mapping_hash, 'road.xodr': road_hash},
        'stationary_candidate_frames': [row['frame'] for row in stationary],
        'bridge_relation_at_rest': [row['bridge_relation'] for row in stationary],
        'traffic_conflict_necessity': 'unverified',
        'law_compliance': 'unverified', 'police_direction': 'unverified',
        'official_device_direction': 'unverified',
        'actual_pixels_verified': False, 'legal_result': None}
    result = {'case_id': config['case_id'],
        'measured_values': {'bridge_relation_at_rest': evidence['bridge_relation_at_rest'],
        'stationary_candidate_frames': evidence['stationary_candidate_frames']},
        'target_checks': [{'target': 'stationary footprint on bridge',
            'requested': wanted, 'measured': full_at_rest,
            'method': 'original Native footprint/deck overlap and observed velocity',
            'tolerance': 'none; full versus no overlap, partial unresolved',
            'matched': matched, 'physical_cause_confirmed': False,
            'cause_evidence': ['bridge-trace.jsonl', 'bridge-map.json', 'video_frames.jsonl']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved original sources measured; bridge support, halt cause, exceptions and pixels require review',
        'physical_failure_flags': ['Physical structure and statutory exceptions unverified'],
        'trace_reference': 'trace.jsonl',
        'video_references': [c + '.mkv' for c in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': evidence, 'realized_observables': {},
        'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    measurements = {
        'bridge_place': {'method': 'place_observation',
            'value': place_observation(rows),
            'sources': {'bridge-map.json': map_hash,
                        'bridge-trace.jsonl': trace_hash,
                        'video_frames.jsonl': mapping_hash}},
        'exception_context': {'method': 'exception_observation',
            'value': exception_observation(trace),
            'sources': {'bridge-trace.jsonl': trace_hash,
                        'road.xodr': road_hash}},
        'bridge_scope': {'method': 'bridge_scope_observation',
            'value': bridge_scope_observation(rows),
            'sources': {'bridge-map.json': map_hash,
                        'bridge-trace.jsonl': trace_hash}}}
    report = {'format': 'c31675-bridge-saved-measurement-v1',
              'case_id': config['case_id'], 'source_hashes': evidence['source_hashes'],
              'measurements': measurements,
              'stationary_candidate_frames': len(stationary),
              'bridge_full_at_rest': full_at_rest,
              'bridge_absent_at_rest': no_bridge_at_rest,
              'requested_target_matched': matched,
              'physical_acceptance_claimed': False, 'legal_result': None}
    Path(output_path).write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))

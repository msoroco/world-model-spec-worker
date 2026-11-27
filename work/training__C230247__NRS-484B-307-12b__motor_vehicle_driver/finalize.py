"""Saved-only source joins and measured Native result for the exact red-X pair."""
import argparse
import hashlib
import json
from pathlib import Path

from lane_red_x_meter import measure
from signal_source import map_inventory

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]

def overhead_red_x(signal_rows, inventory):
    return {'signal_id': inventory['id'], 'governed_lane_id': inventory['lane_id'],
            'mount_m': inventory['mount_m'],
            'red_x_frames': sum(row['signal']['indication'] == 'red_x' for row in signal_rows)}

def facing_driver(measured):
    return measured['red_x_facing_frames']

def lane_occupancy(measured):
    return {'first_overlap_frame': measured['first_governed_lane_overlap_frame'],
            'overlap_frames': measured['governed_lane_overlap_frames'],
            'wholly_inside_frames': measured['governed_lane_wholly_inside_frames']}

def finalize(attempt, output):
    root = Path(attempt)
    cfg = json.loads(required(root, 'config.json').read_text())
    signal_rows = rows(required(root, 'native-signal-rows.jsonl'))
    inventory = map_inventory(required(root, 'native-map-readback.xodr').read_text())
    frame_rows = rows(required(root, 'video_frames.jsonl'))
    trace_rows = rows(required(root, 'trace.jsonl'))
    evidence_rows = rows(required(root, 'capture/evidence.jsonl'))
    for camera in CAMERAS:
        required(root, camera + '.mkv')
    if any(len(seq) != 600 for seq in (signal_rows, frame_rows, trace_rows, evidence_rows)):
        raise ValueError('Full 600-frame original source required')
    for index, (signal, frame, trace, event) in enumerate(zip(signal_rows, frame_rows, trace_rows, evidence_rows)):
        native = signal.get('native_frame')
        if signal.get('frame') != index or frame.get('native_frame') != native or frame.get('carla_frame') != native or trace.get('frame') != native or event.get('original_frame') != native or any(frame.get('camera_native_frames', {}).get(name) != native for name in CAMERAS):
            raise ValueError('Original signal, trace and camera frame join differs')
    measured = measure({'frames': signal_rows})
    if inventory['id'] != 100 or inventory['lane_id'] != -1 or any(
        row['signal']['id'] != inventory['id'] or row['signal']['mount_m'] != inventory['mount_m']
        for row in signal_rows):
        raise ValueError('Original signal source differs from map inventory')
    target_lane = cfg['case']['target_lane_id']
    if target_lane not in (-1, -2) or any(row['vehicle']['proposed_lane_id'] != target_lane for row in signal_rows):
        raise ValueError('Exact target lane differs')
    first = trace_rows[0]['position_m']
    last = trace_rows[-1]['position_m']
    progress = last[0] - first[0]
    if not isinstance(progress, (int, float)) or not math_isfinite(progress):
        raise ValueError('Original travel progress absent')
    entered = measured['first_governed_lane_overlap_frame'] is not None
    diagnostic = signal_rows[0].get('diagnostic_fixture', False)
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    channel_refs = []
    for channel in cfg['recording_description']['channels']:
        name = channel['name']
        path = channels / (name.replace('/', '_') + '.jsonl')
        path.write_text(''.join(json.dumps({
            'time_s': row['time_s'], 'value': int(measured['observations'][index]['governed_lane_overlap']) if name == 'rel.occupies' else {
                'red_x': row['signal']['indication'] == 'red_x',
                'signal_lane_id': row['signal']['lane_id'],
                'actor_lane_id': row['vehicle']['lane_id'],
                'body_vertices_m': row['vehicle']['body_vertices_m'],
                'proposed_lane_id': row['vehicle']['proposed_lane_id']}
        }, separators=(',', ':')) + '\n' for index, row in enumerate(signal_rows)))
        channel_refs.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/' + path.name})
    result = {
        'case_id': cfg['case_id'],
        'measured_values': {'red_x_facing_frames': measured['red_x_facing_frames'],
                            'first_governed_lane_overlap_frame': measured['first_governed_lane_overlap_frame'],
                            'governed_lane_overlap_frames': measured['governed_lane_overlap_frames'],
                            'original_travel_progress_m': progress},
        'target_checks': [
            {'target': 'authored_red_x_lane_entry', 'requested': target_lane == -1,
             'measured': entered, 'method': 'original per-frame body polygon and map-lane intersection',
             'tolerance': 0, 'matched': entered == (target_lane == -1),
             'physical_cause_confirmed': False,
             'cause_evidence': ['native-signal-rows.jsonl', 'native-map-readback.xodr']},
            {'target': 'authored_travel_progress_m', 'requested': 75.0,
             'measured': progress, 'method': 'original trace endpoints', 'tolerance': 1.0,
             'matched': abs(progress - 75.0) <= 1.0,
             'physical_cause_confirmed': False, 'cause_evidence': ['trace.jsonl']}],
        'setup_confirmed': not diagnostic, 'behavior_attempted': not diagnostic,
        'maneuver_completed': not diagnostic and progress >= 40.0,
        'termination_reason': 'full original 600-frame window' if not diagnostic else 'synthetic CPU diagnostic',
        'physical_failure_flags': ['red_x_pixels_official_authority_and_lane_entry_pending_review'],
        'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'], 'recording_evidence': channel_refs,
        'realized_observables': {
            'rel.occupies': {'value': int(entered), 'unit': 'lane overlap',
                             'method': 'original actor body and lane map',
                             'time_window': '600 original frames', 'statistic': 'max',
                             'sample_window_s': [signal_rows[0]['time_s'], signal_rows[-1]['time_s']],
                             'reference': 'channels/rel.occupies.jsonl'},
            'red_x_facing_frames': {'value': measured['red_x_facing_frames'], 'unit': 'frames',
                                    'method': 'original signal and actor orientation join',
                                    'time_window': '600 original frames', 'statistic': 'count',
                                    'reference': 'native-signal-rows.jsonl'},
            'governed_lane_overlap_frames': {'value': measured['governed_lane_overlap_frames'],
                                             'unit': 'frames', 'method': 'original actor body and lane map',
                                             'time_window': '600 original frames', 'statistic': 'count',
                                             'reference': 'native-signal-rows.jsonl'}},
        'provenance_kind': 'synthetic_cpu' if diagnostic else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(root, result)
    report = {
        'format': 'c230247-red-x-saved-analysis-v1', 'case_id': cfg['case_id'],
        'source_sha256': {name: sha(root / name) for name in (
            'native-signal-rows.jsonl', 'native-map-readback.xodr', 'video_frames.jsonl',
            'trace.jsonl', 'capture/evidence.jsonl')},
        'measurements': {
            'overhead_red_x': {'value': overhead_red_x(signal_rows, inventory),
                               'method': 'overhead_red_x',
                               'sources': {name: sha(root / name) for name in
                                           ('native-signal-rows.jsonl', 'native-map-readback.xodr')}},
            'facing_driver': {'value': facing_driver(measured), 'method': 'facing_driver',
                              'sources': {'native-signal-rows.jsonl': sha(root / 'native-signal-rows.jsonl')}},
            'lane_occupancy': {'value': lane_occupancy(measured), 'method': 'lane_occupancy',
                               'sources': {name: sha(root / name) for name in
                                           ('native-signal-rows.jsonl', 'trace.jsonl', 'capture/evidence.jsonl')}},
            'meter': measured},
        'original_native_source': not diagnostic, 'official_authority_review_pending': True,
        'actual_pixels_review_pending': True, 'legal_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report

def math_isfinite(value):
    import math
    return math.isfinite(value)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))

if __name__ == '__main__':
    main()

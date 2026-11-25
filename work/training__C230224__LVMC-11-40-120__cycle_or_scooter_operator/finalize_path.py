"""Finalize saved path-use sources without inferring a legal outcome."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_path import measure as measure_sources

AID = 'training__C230224__LVMC-11-40-120__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('st.bicycle_lane_or_path', 'st.roadway', 'rel.occupies',
            'ru.bicycle', 'ru.electric_bicycle', 'ru.electric_scooter',
            'st.obstruction', 'kin.position')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(root):
    return measure_sources(root)


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    if output.exists() or (root/'result.json').exists():
        raise ValueError('Fresh saved-only stage required')
    required = ('video_frames.jsonl', 'native_rider_trace.jsonl', 'path_context.json')
    for name in required:
        if not (root/name).is_file():
            raise ValueError('Missing required source: '+name)
    observed = measure(root)
    cfg = json.loads((root/'config.json').read_text())
    context = json.loads((root/'path_context.json').read_text())
    frames = records(root/'video_frames.jsonl')
    native = records(root/'native_rider_trace.jsonl')
    if cfg['assignment_id'] != AID or context.get('case_id') != cfg['case_id']:
        raise ValueError('Saved path case identity differs')
    hashes = {name: sha(root/name) for name in required}
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['case_id'],
              'measurements': {'measure': {'method': 'measure', 'value': observed,
                                          'sources': hashes}},
              'legal_verdict_claimed': False}
    trace, channels = [], {name: [] for name in CHANNELS}
    for frame, row in zip(frames, native):
        footprint = row['device_footprint_xy_m']
        x = (min(p[0] for p in footprint)+max(p[0] for p in footprint))/2
        y = (min(p[1] for p in footprint)+max(p[1] for p in footprint))/2
        speed = row['device_speed_mps']
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
                      'position': {'x': x, 'y': y, 'z': 0}, 'position_m': [x, y, 0],
                      'heading_deg': 0, 'speed_mps': speed, 'speed_mph': speed/.44704,
                      'velocity_mps': [speed, 0, 0], 'control': {}})
        values = {
            'st.bicycle_lane_or_path': {'path_polygon_xy_m': context['path_polygon_xy_m'],
                'surface_source': context['path_surface_source'],
                'continuity_source': context['path_continuity_source'],
                'adjacency_source': context['path_adjacency_source'],
                'usability_review_source': context['path_usability_review_source'],
                'path_usable_reviewed': context['path_usable_reviewed']},
            'st.roadway': {'roadway_polygon_xy_m': context['roadway_polygon_xy_m'],
                'boundary_source': context['roadway_boundary_source']},
            'rel.occupies': {'device_footprint_xy_m': footprint,
                'path_occupancy_moving_frames': observed['path_occupancy_moving_frames'],
                'roadway_occupancy_moving_frames': observed['roadway_occupancy_moving_frames']},
            'ru.bicycle': {'device_subtype': context['device_subtype'], 'active': context['device_subtype']=='bicycle',
                'device_subtype_source': context['device_subtype_source']},
            'ru.electric_bicycle': {'device_subtype': context['device_subtype'], 'active': context['device_subtype']=='electric_bicycle',
                'device_subtype_source': context['device_subtype_source']},
            'ru.electric_scooter': {'device_subtype': context['device_subtype'], 'active': context['device_subtype']=='electric_scooter',
                'device_subtype_source': context['device_subtype_source']},
            'st.obstruction': {'path_obstruction_polygon_xy_m': context['path_obstruction_polygon_xy_m'],
                'obstruction_source': context['path_obstruction_source']},
            'kin.position': {'x': x, 'y': y, 'source': 'native_rider_trace.jsonl'},
        }
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    trace_path = root/'trace.jsonl'
    if trace_path.exists():
        if records(trace_path) != trace:
            raise ValueError('Original trace differs from Native rider source')
    else:
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in trace))
    channel_dir = root/'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir/(name+'.jsonl')).write_text(''.join(json.dumps(v, allow_nan=False)+'\n' for v in values))
    intended = 'path' if cfg['case_id'].endswith('probe_01') else 'roadway'
    measured = observed['path_occupancy_moving_frames'] if intended == 'path' else observed['roadway_occupancy_moving_frames']
    result = {'case_id': cfg['case_id'], 'measured_values': observed,
              'target_checks': [{'target': 'measured rider footprint occupancy on '+intended,
                  'requested': intended, 'measured': measured,
                  'method': 'saved original Native footprint intersection with reviewed polygons',
                  'tolerance': 0, 'matched': measured == observed['moving_frame_count'],
                  'physical_cause_confirmed': False, 'cause_evidence': list(hashes)}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False, 'termination_reason': 'original path usability and physical completion review pending',
              'physical_failure_flags': ['independent physical review pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name+'.mkv' for name in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': cfg['recording_description'],
              'recording_evidence': [{'name': channel['name'], 'unit': channel['unit'],
                  'reference': 'channels/'+channel['name']+'.jsonl'} for channel in cfg['recording_description']['channels']] +
                  [{'name': 'path_context', 'unit': 'structured', 'reference': 'path_context.json'}],
              'realized_observables': {}, 'provenance_kind': 'synthetic_fixture',
              'diagnostic_fixture': True, 'accepted': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (root/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

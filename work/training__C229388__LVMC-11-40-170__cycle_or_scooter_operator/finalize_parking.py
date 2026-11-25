"""Finalize recorded parking sources without asserting a legal outcome."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_parking import measure as measure_sources

AID = 'training__C229388__LVMC-11-40-170__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('ru.bicycle', 'ru.electric_bicycle', 'ru.electric_scooter',
    'drv.standing_or_parked', 'st.roadway', 'st.road_edge', 'st.sidewalk',
    'rel.occupies', 'ru.pedestrian', 'rel.surface_gap', 'st.obstruction')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure(root):
    return measure_sources(root)


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Fresh saved-only stage required')
    required = ('video_frames.jsonl', 'native_parking_trace.jsonl', 'parking_context.json')
    for name in required:
        if not (root / name).is_file():
            raise ValueError('Missing required source: ' + name)
    observation = measure(root)
    cfg = json.loads((root / 'config.json').read_text())
    context = json.loads((root / 'parking_context.json').read_text())
    frames, native = records(root / 'video_frames.jsonl'), records(root / 'native_parking_trace.jsonl')
    if cfg['assignment_id'] != AID or context.get('case_id') != cfg['case_id']:
        raise ValueError('Saved parking case identity differs')
    hashes = {name: sha(root / name) for name in required}
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['case_id'],
        'measurements': {'measure': {'method': 'measure', 'value': observation, 'sources': hashes}},
        'legal_verdict_claimed': False}
    trace, channels = [], {name: [] for name in CHANNELS}
    for frame, row in zip(frames, native):
        footprint = row['device_footprint_xy_m']
        x = (min(point[0] for point in footprint) + max(point[0] for point in footprint)) / 2
        y = (min(point[1] for point in footprint) + max(point[1] for point in footprint)) / 2
        speed = row['device_speed_mps']
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
            'position': {'x': x, 'y': y, 'z': 0}, 'position_m': [x, y, 0],
            'heading_deg': 0, 'speed_mps': speed, 'speed_mph': speed / .44704,
            'velocity_mps': [speed, 0, 0], 'control': {}})
        subtype = context['device_subtype']
        values = {
            'ru.bicycle': {'device_subtype': subtype, 'active': subtype == 'bicycle', 'source': context['device_subtype_source']},
            'ru.electric_bicycle': {'device_subtype': subtype, 'active': subtype == 'electric_bicycle', 'source': context['device_subtype_source']},
            'ru.electric_scooter': {'device_subtype': subtype, 'active': subtype == 'electric_scooter', 'source': context['device_subtype_source']},
            'drv.standing_or_parked': {'speed_mps': speed, 'rest_diagnostic': speed <= .05,
                'source': 'native_parking_trace.jsonl'},
            'st.roadway': {'polygon_xy_m': context['roadway_polygon_xy_m'], 'source': context['roadway_geometry_source']},
            'st.road_edge': {'curb_polyline_xy_m': context['curb_polyline_xy_m'], 'source': context['curb_geometry_source']},
            'st.sidewalk': {'polygon_xy_m': context['sidewalk_polygon_xy_m'], 'source': context['sidewalk_geometry_source']},
            'rel.occupies': {'device_footprint_xy_m': footprint, 'source': 'native_parking_trace.jsonl'},
            'ru.pedestrian': {'corridor_polygon_xy_m': context['pedestrian_corridor_polygon_xy_m'],
                'source': context['pedestrian_corridor_source']},
            'rel.surface_gap': {'minimum_m_at_rest': observation['minimum_corridor_gap_m_at_rest'],
                'source': 'native_parking_trace.jsonl,parking_context.json'},
            'st.obstruction': {'corridor_intersection_frames': observation['pedestrian_corridor_intersection_frame_count'],
                'source': 'native_parking_trace.jsonl,parking_context.json'},
        }
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    trace_path = root / 'trace.jsonl'
    if trace_path.exists():
        if records(trace_path) != trace:
            raise ValueError('Original trace differs from Native parking source')
    else:
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in trace))
    channel_dir = root / 'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (channel_dir / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    target = 'rack_clear' if cfg['case_id'].endswith('probe_01') else 'rack_corridor_overlap'
    measured = observation['pedestrian_corridor_intersection_frame_count']
    result = {'case_id': cfg['case_id'], 'measured_values': observation,
        'target_checks': [{'target': 'source-measured rack and pedestrian-corridor placement',
            'requested': target, 'measured': {'rack_frames': observation['rack_intersection_frame_count'],
                'corridor_frames': measured}, 'method': 'Native footprint joined to surveyed polygons',
            'tolerance': 0, 'matched': (measured == 0 if target == 'rack_clear' else measured > 0)
                and observation['rack_intersection_frame_count'] == observation['rest_frame_count'],
            'physical_cause_confirmed': False, 'cause_evidence': list(hashes)}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'original parking geometry, pedestrian obstruction and physical review pending',
        'physical_failure_flags': ['independent physical review pending'],
        'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': [{'name': channel['name'], 'unit': channel['unit'],
            'reference': 'channels/' + channel['name'] + '.jsonl'}
            for channel in cfg['recording_description']['channels']] +
            [{'name': 'parking_context', 'unit': 'structured', 'reference': 'parking_context.json'}],
        'realized_observables': {}, 'provenance_kind': 'synthetic_fixture',
        'diagnostic_fixture': True, 'accepted': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (root / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

"""Finalize saved driveway-sidewalk sources without making a legal judgment."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from sidewalk_saved_measure import measure as measure_sources

AID = 'training__C213851__LVMC-11-40-140__cycle_or_scooter_operator'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('ru.bicycle', 'ru.electric_bicycle', 'ru.electric_scooter', 'st.alley',
            'st.driveway_or_alley_entrance', 'st.sidewalk', 'drv.stopped',
            'drv.crossing_line', 'ru.pedestrian', 'drv.yields_to', 'drv.time_to_conflict')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def in_polygon(x, y, polygon):
    inside = False
    j = len(polygon)-1
    for i, (xi, yi) in enumerate(polygon):
        xj, yj = polygon[j]
        if (yi > y) != (yj > y) and x < (xj-xi)*(y-yi)/(yj-yi)+xi:
            inside = not inside
        j = i
    return inside


def signed_s(x, y, context):
    bx, by = context['sidewalk_boundary_point_xyz_m'][:2]
    dx, dy = context['sidewalk_approach_direction_xyz'][:2]
    length = math.hypot(dx, dy)
    require(length > 0, 'sidewalk approach vector missing')
    return ((x-bx)*dx+(y-by)*dy)/length


def source_packet(frame_map, trace, context, cfg):
    require(len(frame_map) == len(trace) == 600, 'full 600-frame Native trace required')
    converted = []
    for i, (frame, row) in enumerate(zip(frame_map, trace)):
        require(frame['video_frame'] == row['frame'] == i and
                frame['native_frame'] == row['native_frame'], 'original Native frame join differs')
        require(abs(frame['time_s']-row['t_s']) < 1e-4, 'original Native timestamp differs')
        converted.append({'frame': i, 't_s': i/20,
            'rider_id': row['rider_id'], 'pedestrian_id': row['pedestrian_id'],
            'rider_s_m': signed_s(row['rider_x_m'], row['rider_y_m'], context),
            'rider_speed_mps': row['rider_speed_mps'],
            'pedestrian_on_crossing': in_polygon(row['pedestrian_x_m'], row['pedestrian_y_m'],
                                                  context['pedestrian_conflict_polygon_xy_m'])})
    return {'assignment_id': AID, 'source_kind': 'synthetic_native_sample' if
            context['source_kind'] == 'synthetic_native_sample' else 'native_saved_sample',
            'rider_id': trace[0]['rider_id'], 'pedestrian_id': trace[0]['pedestrian_id'],
            'frames': converted}


def measure(root):
    root = Path(root)
    cfg = json.loads((root/'config.json').read_text())
    context = json.loads((root/'sidewalk_context.json').read_text())
    packet = source_packet(rows(root/'video_frames.jsonl'), rows(root/'sidewalk-native.jsonl'),
                           context, cfg)
    site = dict(context)
    site['source_kind'] = packet['source_kind']
    return measure_sources(json.dumps(packet).encode(), json.dumps(site).encode())


def finalize(attempt, output):
    root, output = Path(attempt), Path(output)
    require(not output.exists() and not (root/'result.json').exists(), 'fresh saved-only stage required')
    source_names = ('video_frames.jsonl', 'sidewalk-native.jsonl', 'sidewalk_context.json')
    for name in source_names:
        require((root/name).is_file(), 'Missing required source: '+name)
    cfg = json.loads((root/'config.json').read_text())
    context = json.loads((root/'sidewalk_context.json').read_text())
    require(cfg['assignment_id'] == AID and context['assignment_id'] == AID and
            context['case_id'] == cfg['case_id'], 'saved sidewalk identity differs')
    frame_map, native = rows(root/'video_frames.jsonl'), rows(root/'sidewalk-native.jsonl')
    packet = source_packet(frame_map, native, context, cfg)
    site = dict(context)
    site['source_kind'] = packet['source_kind']
    observation = measure_sources(json.dumps(packet).encode(), json.dumps(site).encode())
    hashes = {name: sha(root/name) for name in source_names}
    trace, channels = [], {name: [] for name in CHANNELS}
    for frame, row, derived in zip(frame_map, native, packet['frames']):
        speed = row['rider_speed_mps']
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
            'position': {'x': row['rider_x_m'], 'y': row['rider_y_m'], 'z': 0},
            'position_m': [row['rider_x_m'], row['rider_y_m'], 0],
            'heading_deg': 0, 'speed_mps': speed, 'speed_mph': speed/.44704,
            'velocity_mps': [speed, 0, 0], 'control': {}})
        subtype = context['rider_class']
        values = {'ru.bicycle': {'active': subtype == 'bicycle', 'source': context['rider_class_source_id']},
            'ru.electric_bicycle': {'active': subtype == 'electric_bicycle', 'source': context['rider_class_source_id']},
            'ru.electric_scooter': {'active': subtype == 'electric_scooter', 'source': context['rider_class_source_id']},
            'st.alley': {'active': context['origin_kind']=='alley', 'source': context['origin_source_id']},
            'st.driveway_or_alley_entrance': {'origin_kind': context['origin_kind'], 'source': context['origin_source_id']},
            'st.sidewalk': {'continuous': context['sidewalk_continuation_across_origin'],
                'source': context['sidewalk_continuation_source_id']},
            'drv.stopped': {'speed_mps': speed, 'near_zero_diagnostic': speed <= .1,
                'source': 'sidewalk-native.jsonl'},
            'drv.crossing_line': {'signed_distance_m': derived['rider_s_m'],
                'source': context['sidewalk_boundary_source_id']},
            'ru.pedestrian': {'actor_id': row['pedestrian_id'],
                'on_conflict_polygon': derived['pedestrian_on_crossing'],
                'source': context['pedestrian_conflict_source_id']},
            'drv.yields_to': {'pre_entry_near_zero_frames': observation['pre_entry_near_zero_frames'],
                'pedestrian_on_crossing_at_entry': observation['pedestrian_on_crossing_at_entry'],
                'source': 'sidewalk-native.jsonl,sidewalk_context.json'},
            'drv.time_to_conflict': {'legal_necessity_unresolved': True,
                'source': 'sidewalk-native.jsonl,sidewalk_context.json'}}
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    trace_path = root/'trace.jsonl'
    if trace_path.exists():
        original_trace = rows(trace_path)
        require(len(original_trace) == len(trace), 'original trace frame count differs')
        for original, derived in zip(original_trace, trace):
            require(original.get('frame') == derived['frame'] and
                abs(original.get('time_s', -1)-derived['time_s']) < 1e-4 and
                len(original.get('position_m', [])) >= 2 and
                all(abs(a-b) < 1e-3 for a,b in zip(original['position_m'][:2],
                    derived['position_m'][:2])) and
                abs(original.get('speed_mps', -1)-derived['speed_mps']) < 1e-3,
                'original trace differs from Native sidewalk source')
    else:
        trace_path.write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in trace))
    channel_dir = root/'channels'
    channel_dir.mkdir(exist_ok=True)
    for name, values in channels.items():
        (channel_dir/(name+'.jsonl')).write_text(''.join(json.dumps(value, allow_nan=False)+'\n' for value in values))
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['case_id'],
        'measurements': {'measure': {'method': 'measure', 'value': observation, 'sources': hashes}},
        'legal_verdict_claimed': False}
    requested = 'stop_and_yield' if cfg['case_id'].endswith('probe_01') else 'roll_through'
    stop = bool(observation['pre_entry_near_zero_frames'])
    matched = stop if requested == 'stop_and_yield' else not stop
    result = {'case_id': cfg['case_id'], 'measured_values': observation,
        'target_checks': [{'target': 'source-measured pre-sidewalk stop and pedestrian conflict',
            'requested': requested,
            'measured': {'stop_before_entry': stop,
                'pedestrian_on_crossing_at_entry': observation['pedestrian_on_crossing_at_entry']},
            'method': 'Native rider and pedestrian poses joined to source-reviewed sidewalk geometry',
            'tolerance': None, 'matched': matched,
            'physical_cause_confirmed': False, 'cause_evidence': list(hashes)}],
        'setup_confirmed': False, 'behavior_attempted': True, 'maneuver_completed': False,
        'termination_reason': 'original sidewalk, stop and pedestrian conflict review pending',
        'physical_failure_flags': ['independent original-source review pending'],
        'trace_reference': 'trace.jsonl', 'video_references': [name+'.mkv' for name in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': cfg['recording_description'],
        'recording_evidence': [{'name': item['name'], 'unit': item['unit'],
            'reference': 'channels/'+item['name']+'.jsonl'}
            for item in cfg['recording_description']['channels']] +
            [{'name': 'sidewalk_context', 'unit': 'structured', 'reference': 'sidewalk_context.json'}],
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

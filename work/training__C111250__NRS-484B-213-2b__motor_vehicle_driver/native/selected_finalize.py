"""Recompute selected intersection-zone observations from saved source rows."""
import argparse
import hashlib
import json
from pathlib import Path

from zone_measure import measure

SOURCES = ('road-context.json', 'vehicle-footprints.jsonl', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure_zone(metric):
    return {key: metric[key] for key in ('frames', 'first_active_frame',
        'first_left_active_frame', 'first_left_approach_frame',
        'first_left_traversal_frame', 'one_way_highway',
        'subsection_2_applicability')}


def value(name, body, context):
    corners = body['body_xy_m']
    front = max(point[0] for point in corners)
    rear = min(point[0] for point in corners)
    entry, exit = context['intersection_x_m']
    if name == 'st.intersection':
        return [entry, exit]
    if name == 'st.railway_crossing':
        return bool(context.get('railroad_crossing_claimed', False))
    if name == 'drv.approaching':
        return entry - 30.48 <= front < entry and rear < entry
    if name == 'rel.centre_distance':
        return entry - front
    if name == 'st.centre_line':
        return context['centerline_y_m']
    if name == 'rel.occupies':
        return any(point[1] > context['centerline_y_m'] for point in corners)
    if name == 'drv.in_intersection':
        return front >= entry and rear <= exit
    if name == 'st.one_way_roadway':
        return context['one_way_highway']
    raise ValueError('Unsupported selected observation: ' + name)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['case_id']
    if case != construction['case_id'] or case not in config['supported_case_ids']:
        raise ValueError('Exact selected case differs')
    metric = measure(attempt)
    bodies = rows(attempt / 'vehicle-footprints.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    if len(bodies) != len(frame_map) or len(trace) != 600:
        raise ValueError('Saved original row count differs')
    for body, mapping, pose in zip(bodies, frame_map, trace):
        if (body.get('original_carla_frame', body['native_frame']) != mapping['native_frame'] or
                pose['frame'] != mapping.get('carla_frame', mapping['native_frame']) or
                abs(body['time_s'] - mapping['time_s']) > 1e-6):
            raise ValueError('Saved footprint/trace/video join differs')
    context = json.loads((attempt / 'road-context.json').read_text())
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for body, mapping in zip(bodies, frame_map):
                stream.write(json.dumps({'time_s': mapping['time_s'],
                                         'value': value(name, body, context)},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    for context_input in construction['recording_description']['context_inputs']:
        if context_input['name'] != 'two_way_intersection_source':
            raise ValueError('Unknown source context input')
        evidence.append({'name': context_input['name'], 'unit': context_input['unit'],
                         'reference': 'road-context.json'})
    diagnostic = context.get('source_kind') == 'synthetic_cpu_diagnostic'
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'zone_measurement': {'method': 'measure_zone',
                  'value': measure_zone(metric), 'sources': source_hashes}},
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    requested_left = bool(config['requested_left_interval'])
    seen_left = metric['first_left_active_frame'] is not None
    result = {'case_id': case, 'measured_values': measure_zone(metric),
              'target_checks': [{'target': 'left-side footprint during active intersection zone',
                  'requested': requested_left, 'measured': seen_left,
                  'method': 'measure_zone', 'tolerance': 0,
                  'matched': requested_left == seen_left,
                  'physical_cause_confirmed': False,
                  'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': not diagnostic,
              'maneuver_completed': False,
              'termination_reason': '600-frame diagnostic' if diagnostic else '600-frame original Native attempt',
              'physical_failure_flags': ['Original roadway/pixels and legal interpretation pending'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_native_attempt',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

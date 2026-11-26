"""Saved-only source-joined outside-crosswalk crossing metering."""
import argparse
import hashlib
import json
from pathlib import Path

from crossing_meter import measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def crossing_measurement(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved result; use a fresh attempt')
    sources = ('post-tick.jsonl', 'crossing-context.json', 'video_frames.jsonl',
               'trace.jsonl', 'capture/evidence.jsonl')
    videos = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
    for name in (*sources, *videos, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['selected_case_id']
    if case != construction['case_id'] or case not in {
            config['assignment_id'] + '__probe_01',
            config['assignment_id'] + '__probe_02'}:
        raise ValueError('Saved crossing case identity differs')
    measured = crossing_measurement(attempt)
    rows = [json.loads(line) for line in (attempt / 'post-tick.jsonl').read_text().splitlines()]
    frame_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    evidence = [json.loads(line) for line in (attempt / 'capture/evidence.jsonl').read_text().splitlines()]
    if not all(len(part) == 600 for part in (rows, frame_map, trace, evidence)):
        raise ValueError('Full 600-frame original source join required')
    for index, (row, mapped, state, capture) in enumerate(zip(rows, frame_map, trace, evidence)):
        frame = row['native_frame']
        if (mapped['video_frame'] != index or mapped['carla_frame'] != frame or
                state['frame'] != frame or capture['original_frame'] != frame or
                abs(row['time_s'] - mapped['time_s']) > 1e-4 or
                abs(state['time_s'] - mapped['time_s']) > 1e-4 or
                abs(capture['recording_time_s'] - mapped['time_s']) > 1e-4 or
                capture['actor_id'] != row['pedestrian_id']):
            raise ValueError('Original pedestrian/frame/capture join differs')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    recording_evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        target = channels / (name + '.jsonl')
        with target.open('x') as stream:
            for row in rows:
                value = (row['pedestrian_id'] if name == 'ru.subject' else
                         row['pedestrian_footprint_xy_m'] if name in ('rel.occupies', 'st.roadway') else
                         row['vehicles'] if name.startswith('drv.') else
                         json.loads((attempt / 'crossing-context.json').read_text()).get(
                             'intersection_intervals_y_m' if name == 'st.intersection' else
                             'marked_crosswalk_intervals_y_m'))
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
        recording_evidence.append({'name': name, 'unit': channel['unit'],
                                   'reference': 'channels/' + target.name})
    source_hashes = {name: sha(attempt / name) for name in ('post-tick.jsonl', 'crossing-context.json')}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'crossing_measurement': {'method': 'crossing_measurement',
                  'value': measured, 'sources': source_hashes}},
              'source_complete': True, 'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'outside-crosswalk roadway entry and source-measured vehicle precedence',
                  'requested': config['pedestrian_departure_frame'],
                  'measured': measured['roadway_entry_frame'], 'method': 'crossing_measurement',
                  'tolerance': 0,
                  'matched': measured['roadway_entry_frame'] == config['pedestrian_departure_frame'],
                  'physical_cause_confirmed': False,
                  'cause_evidence': list(source_hashes)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved crossing sources measured; original physical and Section 11.30.070 review pending',
              'physical_failure_flags': ['Physical crossing and actual camera pixels unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(videos),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': recording_evidence, 'realized_observables': {},
              'provenance_kind': 'original_source_review' if measured['source_kind'] == 'native_post_tick' else 'synthetic_local_diagnostic',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

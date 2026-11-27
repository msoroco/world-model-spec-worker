"""Measure only sealed, saved original rail and vehicle sources."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_rail import measure
from source_review import ROLES, load as load_review

AID = 'training__C202465__NRS-484B-560-7a__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('st.railway_crossing', 'drv.crossing_line', 'drv.cleared_line',
            'kin.extent', 'drv.stopped', 'rel.surface_gap', 'drv.following',
            'st.grade', 'kin.velocity')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def analyze(attempt):
    attempt = Path(attempt)
    required = ('config.json', 'road.xodr', 'vehicle-extent.json', 'rail-context.json',
                'rail-actors.jsonl', 'trace.jsonl', 'video_frames.jsonl',
                'sources.json', 'acquisition-provenance.json',
                *(camera + '.mkv' for camera in CAMERAS),
                *('rail-review/' + role + ending for role in ROLES
                  for ending in ('.json', '.source.txt')))
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case = config.get('case_id', '')
    if (not case.startswith(AID + '__') or config.get('selected_case_id') != case
            or config.get('law_id') != 'NRS-484B-560-7a'
            or config.get('cell_id') != 'C202465'
            or config.get('actor') != 'motor_vehicle_driver'
            or config.get('rate_hz') != 20 or config.get('duration_s') != 30):
        raise ValueError('Exact saved rail case identity differs')
    road_sha = sha(attempt / 'road.xodr')
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = provenance.get('provenance_kind') == 'synthetic_fixture'
    reviewed = load_review(attempt / 'rail-review', road_sha,
                           diagnostic_fixture=diagnostic)
    context = json.loads((attempt / 'rail-context.json').read_text())
    if (context.get('native_map_sha256') != road_sha
            or context.get('rail_geometry_sha256') != sha(attempt / 'rail-review/rail-geometry.json')
            or context.get('vehicle_extent_sha256') != sha(attempt / 'vehicle-extent.json')
            or context.get('opposite_space_source_sha256') != sha(attempt / 'rail-review/opposite-space.source.txt')
            or context.get('undercarriage_source_sha256') != sha(attempt / 'rail-review/undercarriage-grade.source.txt')
            or context.get('entry_rail_x_m') != reviewed['rail-geometry']['entry_rail_x_m']
            or context.get('clearance_reference_rail_x_m') != reviewed['rail-geometry']['clearance_reference_rail_x_m']):
        raise ValueError('Saved rail source hash or reviewed geometry differs')
    actor_rows = rows(attempt / 'rail-actors.jsonl')
    frame_rows = rows(attempt / 'video_frames.jsonl')
    if len(actor_rows) != 600 or len(frame_rows) != 600:
        raise ValueError('Incomplete 600-frame original rail source join')
    for index, (actor, frame) in enumerate(zip(actor_rows, frame_rows)):
        if (actor.get('video_frame') != index or frame.get('video_frame') != index
                or actor.get('native_frame') != frame.get('native_frame')
                or actor.get('camera_native_frames') != frame.get('camera_native_frames')):
            raise ValueError('Original rail actor and camera frame join differs')
    observed = measure(context, actor_rows)
    return {'config': config, 'context': context, 'rows': actor_rows,
            'measured': observed,
            'source_sha256': {name: sha(attempt / name) for name in required},
            'diagnostic_fixture': diagnostic}


def measurement_item(data, value, method, names):
    source = data['source_sha256']
    return {'value': value, 'method': method,
            'sources': {name: source[name] for name in names}}


def measure_opposite_space(data):
    observed = data['measured']
    return measurement_item(data, {
        'pre_entry_space_m': observed['pre_entry_opposite_space_m'],
        'preclear_stop_frames': observed['stopped_before_15_foot_clearance_frames'],
        'cause_observed_frames': observed['opposite_space_cause_observed_frames'],
        'legal_result': None}, 'measure_opposite_space',
        ('road.xodr', 'rail-review/opposite-space.json',
         'rail-review/opposite-space.source.txt', 'rail-actors.jsonl',
         'video_frames.jsonl'))


def measure_undercarriage(data):
    observed = data['measured']
    return measurement_item(data, {
        'clearance_alternative': observed['undercarriage_clearance_alternative'],
        'cause_observed_frames': observed['undercarriage_cause_observed_frames'],
        'legal_result': None}, 'measure_undercarriage',
        ('road.xodr', 'rail-review/undercarriage-grade.json',
         'rail-review/undercarriage-grade.source.txt', 'vehicle-extent.json',
         'rail-actors.jsonl'))


def measure_complete_crossing(data):
    observed = data['measured']
    return measurement_item(data, {
        'max_trailing_clearance_m': observed['maximum_trailing_end_clearance_past_reference_rail_m'],
        'trailing_end_reached_15_feet': observed['trailing_end_reached_15_feet'],
        'legal_result': None}, 'measure_complete_crossing',
        ('rail-review/rail-geometry.json', 'rail-review/rail-geometry.source.txt',
         'vehicle-extent.json', 'rail-actors.jsonl', 'video_frames.jsonl'))


def output_measurements(data):
    return {'opposite_space': measure_opposite_space(data),
            'undercarriage': measure_undercarriage(data),
            'complete_crossing': measure_complete_crossing(data)}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior saved rail measurement')
    data = analyze(attempt)
    measurements = output_measurements(data)
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    for channel in CHANNELS:
        with (channels / (channel + '.jsonl')).open('x') as stream:
            for row in data['rows']:
                value = {'native_frame': row['native_frame'],
                         'vehicle_footprint_m': row['vehicle_footprint_m'],
                         'observed_speed_mps': row['observed_speed_mps'],
                         'queue_body_m': row['queue_body_m'],
                         'rail_entry_x_m': data['context']['entry_rail_x_m'],
                         'rail_clearance_reference_x_m': data['context']['clearance_reference_rail_x_m'],
                         'stop_cause_source': row['stop_cause_source']}
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value}) + '\n')
    observed = data['measured']
    result = {'case_id': data['config']['case_id'],
              'measured_values': {'rail_crossing': {'value': observed,
                                                   'source_hashes': data['source_sha256'],
                                                   'legal_result': None}},
              'target_checks': [{'target': 'source-bound complete crossing and stop cause',
                                 'requested': data['config']['case_id'], 'measured': observed,
                                 'method': 'saved original rail/body/queue/video join',
                                 'tolerance': 0, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(data['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': observed['trailing_end_reached_15_feet'],
              'termination_reason': 'Saved rail measurement complete; physical cause and legal judgment pending',
              'physical_failure_flags': ['independent_original_stop_cause_review_pending'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera + '.mkv' for camera in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': data['config']['recording_description'],
              'recording_evidence': [{'name': channel, 'unit': 'structured',
                                      'reference': 'channels/' + channel + '.jsonl'}
                                     for channel in CHANNELS],
              'realized_observables': {'trailing_end_clearance_m': {
                  'value': observed['maximum_trailing_end_clearance_past_reference_rail_m'], 'unit': 'm',
                  'method': 'source-reviewed original body and rail geometry',
                  'time_window': '600 joined Native frames', 'statistic': 'any after entry',
                  'reference': 'channels/drv.cleared_line.jsonl'}},
              'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c202465-saved-source-rail-measurements-v1',
              'case_id': data['config']['case_id'], 'measurements': measurements,
              'diagnostic': {'source_sha256': data['source_sha256'],
                             'diagnostic_fixture': data['diagnostic_fixture']},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    arguments = parser.parse_args()
    print(json.dumps(finalize(arguments.attempt, arguments.output), sort_keys=True))

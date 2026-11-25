"""Saved-only source join and Native result writer for crosswalk cases."""
import argparse
import hashlib
import json
from pathlib import Path

from finalize_crosswalk import finalize as diagnose


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_crosswalk_position(diagnostic, sources):
    frames = diagnostic['halt_proxy_frames']
    if not frames:
        raise ValueError('Original stopped interval missing')
    return {'value': {'minimum_body_gap_m': min(diagnostic['body_to_crosswalk_m_by_frame'][i] for i in frames),
                      'minimum_center_gap_m': min(diagnostic['center_to_crosswalk_m_by_frame'][i] for i in frames),
                      'sampled_halt_spans': diagnostic['halt_proxy_spans'],
                      'statutory_20_feet_m': diagnostic['statutory_20_feet_m'],
                      'legal_result': None},
            'method': 'measure_crosswalk_position', 'sources': sources}


def finalize(attempt, output):
    from worker_exchange.native_output import write_result

    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis report or result')
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config['case_id']
    if config.get('selected_case_id') != case_id or config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('Exact case capture contract differs')
    source_names = ('vehicle-poses.jsonl', 'control-intent.jsonl', 'video_frames.jsonl',
                    'crosswalk-inventory.json', 'crosswalk-source-review.json')
    for name in (*source_names, 'trace.jsonl'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    diagnostic = diagnose(attempt)
    sources = {name: sha(attempt / name) for name in source_names}
    poses = [json.loads(line) for line in (attempt / 'vehicle-poses.jsonl').read_text().splitlines()]
    controls = [json.loads(line) for line in (attempt / 'control-intent.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Derived channels already exist')
    channels.mkdir()
    values = {
        'subject_vehicle_pose_and_extent': [p for p in poses],
        'control_intent': [c['applied_control'] for c in controls],
        'frame_join': [{'native_frame': m['native_frame'],
                        'camera_native_frames': m['camera_native_frames']} for m in mapping],
    }
    for name, items in values.items():
        with (channels / (name + '.jsonl')).open('x') as stream:
            for index, value in enumerate(items):
                stream.write(json.dumps({'time_s': mapping[index]['time_s'], 'value': value}) + '\n')
    context = {'crosswalk_extent': diagnostic['crosswalk_rect_xyxy_m'],
               'source_sha256': sources}
    (channels / 'crosswalk_extent.json').write_text(json.dumps(context, indent=2) + '\n')
    for name, digest in sources.items():
        if sha(attempt / name) != digest:
            raise ValueError('Finalizer changed original source: ' + name)
    measurement = measure_crosswalk_position(diagnostic, {name: sources[name] for name in
                                  ('vehicle-poses.jsonl', 'crosswalk-inventory.json',
                                   'crosswalk-source-review.json')})
    body_gap = measurement['value']['minimum_body_gap_m']
    expected = {'controlled_1': 12.0, 'controlled_2': 3.0,
                'boundary_20ft': 6.096, 'stop_near': 3.0, 'stand_near': 3.0}[config['crosswalk_case']]
    observed_halt = bool(diagnostic['halt_proxy_spans'])
    result = {'case_id': case_id,
              'measured_values': {'crosswalk_distance': measurement['value'],
                                  'engineering_action': diagnostic['engineering_action']},
              'target_checks': [{'target': 'observed stopped body gap to marked crosswalk',
                                 'requested': expected, 'measured': body_gap,
                                 'method': 'minimum original body polygon gap during sampled halt',
                                 'tolerance': 1.0, 'matched': abs(expected-body_gap) <= 1.0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(sources)}],
              'setup_confirmed': False, 'behavior_attempted': observed_halt,
              'maneuver_completed': False,
              'termination_reason': 'Saved original-frame geometry measured; physical and marking review pending',
              'physical_failure_flags': ['actual_motion_marking_pixels_and_exceptions_unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [{'name': item['name'], 'unit': item['unit'],
                  'reference': 'channels/' + item['name'] + ('.jsonl' if item in config['recording_description']['channels'] else '.json')}
                  for item in config['recording_description']['channels'] +
                              config['recording_description']['context_inputs']],
              'realized_observables': {'minimum_body_gap_m': {'value': body_gap,
                  'unit': 'm', 'method': 'minimum sampled halt body polygon gap',
                  'time_window': 'all sampled halted frames', 'statistic': 'min',
                  'reference': 'channels/subject_vehicle_pose_and_extent.jsonl'}},
              'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report = {'format': 'c229397-saved-delivery-measurements-v1', 'case_id': case_id,
              'measurements': {'crosswalk_position': measurement},
              'diagnostic': diagnostic, 'source_sha256': sources,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

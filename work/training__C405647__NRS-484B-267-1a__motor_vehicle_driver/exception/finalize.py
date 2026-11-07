"""Case-specific saved exception measurement; no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

SOURCES = ('source-scope.json', 'actor-frames.jsonl')
VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'rear_approach.mkv',
          'subject_reference.mkv', 'officer_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def officer_direction_and_approach_timing(folder):
    return measure(folder)


def analysis_report(folder):
    folder = Path(folder)
    for name in SOURCES:
        if not (folder / name).is_file():
            raise ValueError('Missing required source: ' + name)
    scope = json.loads((folder / 'source-scope.json').read_text())
    case = scope.get('case_suffix')
    if case not in ('exception_1_1', 'exception_1_2'):
        raise ValueError('Unknown exception case')
    return {'format': 'c405647-exception-saved-analysis-v1',
            'case_id': 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver__' + case,
            'selected': False, 'draft_only': True,
            'measurements': {'officer_direction_timing': {
                'method': 'officer_direction_and_approach_timing',
                'value': officer_direction_and_approach_timing(folder),
                'sources': {name: sha(folder / name) for name in SOURCES}}},
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh output')
    report = analysis_report(attempt)
    config_path = attempt / 'config.json'
    if not config_path.is_file():
        output.write_text(json.dumps(report, indent=2) + '\n')
        return report
    from worker_exchange.native_output import validate_result
    for name in ('construction.json', 'trace.jsonl', 'video_frames.jsonl', *VIDEOS):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads(config_path.read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    if config.get('case_id') != report['case_id'] or \
            construction.get('case_id') != report['case_id']:
        raise ValueError('Exact case/configuration differs')
    scope = json.loads((attempt / 'source-scope.json').read_text())
    inventory = scope.get('native_source_hashes')
    if not isinstance(inventory, dict) or not inventory:
        raise ValueError('Saved source inventory absent')
    for name, expected in inventory.items():
        path = attempt / name
        if not path.is_file() or sha(path) != expected:
            raise ValueError('Saved source hash differs: ' + name)
    def rows(path):
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    actors = rows(attempt / 'actor-frames.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    count = config['duration_s'] * config['rate_hz']
    if len(actors) != len(mapping) or len(mapping) != len(trace) or len(trace) != count:
        raise ValueError('Saved actor/trace/video frame counts differ')
    for index, (actor, frame, point) in enumerate(zip(actors, mapping, trace)):
        native_frame = actor.get('native_frame')
        if actor.get('frame') != index or actor.get('video_frame') != index or \
                frame.get('video_frame') != index or frame.get('native_frame') != native_frame or \
                point.get('frame') != native_frame or \
                abs(float(frame['time_s']) - float(point['time_s'])) > 1e-6:
            raise ValueError('Saved actor/trace/video frame join differs')
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Retain prior channels; use a fresh attempt')
    channels.mkdir()
    native_requests = rows(attempt / 'native-requests.jsonl')
    if len(native_requests) != count:
        raise ValueError('Saved Native request count differs')
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for actor, frame in zip(actors, mapping):
                values = {
                    'subject_pose_body': {'subject': actor['subject'],
                                          'body_xy_m': actor['subject_body_xy_m']},
                    'approach_pose_body': actor['approach'],
                    'officer_visual_pose': {'requested_xy_m':
                        native_requests[actor['frame']]['officer_position_request_xy_m'],
                        'identity_verified': False},
                    'requested_direction': {'requested': actor['direction_requested'],
                                            'review': actor['direction_review']},
                    'camera_frame_join': {'native_frame': frame['native_frame'],
                                          'video_frame': frame['video_frame']}}
                stream.write(json.dumps({'time_s': frame['time_s'],
                                         'value': values[name]}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    measurement = report['measurements']['officer_direction_timing']['value']
    expected = config['case_suffix'] == 'exception_1_2'
    observed = measurement['cue_overlaps_request']
    result = {'case_id': report['case_id'],
              'measured_values': {key: value for key, value in measurement.items()
                                  if key != 'legal_exception_verdict'},
              'target_checks': [{'target': 'synthetic cue overlaps requested direction',
                                 'requested': expected, 'measured': observed,
                                 'method': 'source-bound saved cue and request frame overlap',
                                 'tolerance': 'one 50 ms retained frame',
                                 'matched': observed == expected,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['actor-frames.jsonl',
                                                    'direction-review.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full diagnostic 480-frame saved window',
              'physical_failure_flags': ['Officer identity, communication and authority unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'synthetic_cue_frames': {
                  'value': measurement['synthetic_cue_frames'], 'unit': 'count',
                  'method': 'saved source-bound synthetic cue review',
                  'time_window': 'entire 24 s saved window', 'statistic': 'count',
                  'reference': 'actor-frames.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    validate_result(result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

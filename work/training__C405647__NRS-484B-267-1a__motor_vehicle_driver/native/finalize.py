"""Case-specific saved C405647 motion analysis; no legal or physical verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

SOURCES = ('source-scope.json', 'actor-frames.jsonl')
VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'rear_approach.mkv',
          'subject_reference.mkv')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approach_clearance_and_lamp_timing(folder):
    return measure(folder)


def analysis_report(folder):
    folder = Path(folder)
    for name in SOURCES:
        if not (folder / name).is_file():
            raise ValueError('Missing required source: ' + name)
    scope = json.loads((folder / 'source-scope.json').read_text())
    suffix = scope.get('case_suffix')
    if suffix not in ('witness_1', 'witness_2'):
        raise ValueError('Unknown controlled case')
    return {
        'format': 'c405647-1a-saved-analysis-v1',
        'case_id': 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver__' + suffix,
        'selected': False, 'draft_only': True,
        'measurements': {'emergency_approach_clearance': {
            'method': 'approach_clearance_and_lamp_timing',
            'value': approach_clearance_and_lamp_timing(folder),
            'sources': {name: _sha(folder / name) for name in SOURCES}}},
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False
    }


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def finalize(attempt, output):
    """Finish a saved diagnostic package without claiming Native acceptance."""
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
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
    if config.get('case_id') != report['case_id'] or construction.get('case_id') != report['case_id']:
        raise ValueError('Exact case/configuration differs')
    scope = json.loads((attempt / 'source-scope.json').read_text())
    source_hashes = scope.get('native_source_hashes')
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError('Saved Native source inventory absent')
    for name, expected in source_hashes.items():
        path = attempt / name
        if not path.is_file() or _sha(path) != expected:
            raise ValueError('Saved Native source hash differs: ' + name)
    count = config['duration_s'] * config['rate_hz']
    actors = _rows(attempt / 'actor-frames.jsonl')
    mapping = _rows(attempt / 'video_frames.jsonl')
    trace = _rows(attempt / 'trace.jsonl')
    if len(actors) != len(mapping) or len(mapping) != len(trace) or len(trace) != count:
        raise ValueError('Saved actor/trace/video frame counts differ')
    first_time = mapping[0]['time_s']
    for index, (actor, frame, point) in enumerate(zip(actors, mapping, trace)):
        native_frame = actor.get('native_frame')
        if (actor.get('frame') != index or actor.get('video_frame') != index or
                frame.get('video_frame') != index or frame.get('native_frame') != native_frame or
                frame.get('carla_frame') != native_frame or point.get('frame') != native_frame or
                abs(float(frame['time_s']) - float(point['time_s'])) > 1e-6 or
                abs(float(frame['time_s']) - first_time - index / config['rate_hz']) > .01):
            raise ValueError('Saved actor/trace/video frame join differs')
    measurement = report['measurements']['emergency_approach_clearance']['value']
    observed = measurement['full_body_cleared_before_catchup']
    requested = config['case_suffix'] == 'witness_1'
    channels = attempt / 'channels'
    if channels.exists():
        raise ValueError('Retain prior recording channels; use a fresh attempt')
    channels.mkdir()
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
                    'light_state': {'front_red_flash_on': actor['front_red_flash_on']},
                    'camera_frame_join': {'native_frame': frame['native_frame'],
                                          'video_frame': frame['video_frame']}}
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': values[name]}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    result = {'case_id': report['case_id'],
              'measured_values': {key: value for key, value in measurement.items()
                                  if key != 'legal_immediacy_or_yield_verdict'},
              'target_checks': [{'target': 'full-body inner-lane clearance before approach catch-up',
                                 'requested': requested, 'measured': observed,
                                 'method': 'saved four-vertex footprint and longitudinal gap',
                                 'tolerance': 'one 50 ms retained frame',
                                 'matched': observed == requested,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['actor-frames.jsonl', 'source-scope.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full diagnostic 480-frame saved window',
              'physical_failure_flags': ['Native behavior and authority unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'lamp_transitions': {
                  'value': measurement['observed_lamp_transitions'], 'unit': 'count',
                  'method': 'saved source-bound front-lamp review transitions',
                  'time_window': 'entire 24 s saved window', 'statistic': 'count',
                  'reference': 'actor-frames.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)

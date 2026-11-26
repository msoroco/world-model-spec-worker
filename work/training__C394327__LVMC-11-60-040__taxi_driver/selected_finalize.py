"""Measure reviewed taxi activity from joined saved sources, without legal inference."""
import argparse
import hashlib
import json
from pathlib import Path

from taxi_loading import FRAMES, VIEWS, measure


MEASUREMENT_INPUTS = ('observed-activity.jsonl',
                      'participant-activity-review.json',
                      'stand-designation-review.json',
                      'other-regulations-review.json')
SOURCE_INPUTS = ('native-rows.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                 'capture/evidence.jsonl', 'taxi-license-review.json',
                 *MEASUREMENT_INPUTS, *(view + '.mkv' for view in VIEWS))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def taxi_loading_measurement(attempt):
    attempt = Path(attempt)
    for name in MEASUREMENT_INPUTS:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    for name in ('taxi-license-review.json', 'native-rows.jsonl',
                 'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    native = rows(attempt / 'native-rows.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    capture = rows(attempt / 'capture/evidence.jsonl')
    activity = rows(attempt / 'observed-activity.jsonl')
    if any(len(part) != FRAMES for part in (native, mapping, trace, capture, activity)):
        raise ValueError('Full 600-frame saved source join required')
    for name in MEASUREMENT_INPUTS[1:] + ('taxi-license-review.json',):
        review = json.loads((attempt / name).read_text())
        if not review.get('source_basis') or review.get('legal_verdict') is not None:
            raise ValueError('Reviewed source basis missing: ' + name)
    measured_rows = []
    for index, (n, m, t, c, a) in enumerate(zip(native, mapping, trace,
                                                  capture, activity)):
        frame = n.get('native_frame')
        time_s = n.get('time_s')
        if (n.get('video_frame') != index or m.get('video_frame') != index or
                a.get('video_frame') != index or m.get('carla_frame') != frame or
                t.get('frame') != frame or c.get('original_frame') != frame or
                a.get('native_frame') != frame or
                any(abs(item.get('time_s', -1) - time_s) > 1e-4
                    for item in (m, t, a)) or
                abs(c.get('recording_time_s', -1) - time_s) > 1e-4 or
                t.get('taxi_actor_id') != n.get('taxi_actor_id') or
                c.get('actor_id') != n.get('taxi_actor_id')):
            raise ValueError('Taxi, activity, trace and camera frame join differs')
        cameras = m.get('camera_native_frames')
        if (not isinstance(cameras, dict) or set(cameras) != set(VIEWS) or
                any(value != frame for value in cameras.values()) or
                n.get('source_cameras') != cameras):
            raise ValueError('Four original taxi camera frame joins required')
        measured_rows.append({
            'frame': index, 'time_s': (index + 1) / 20,
            'source_kind': 'original_native',
            **{key: a.get(key) for key in ('observed_taxi_identity',
                'observed_stand_location', 'observed_speed_mps',
                'observed_door_open', 'observed_occupant_count',
                'observed_activity')},
            'original_source': {
                'native_capture_path': 'native-rows.jsonl',
                'native_capture_sha256': sha(attempt / 'native-rows.jsonl'),
                'participant_review_path': 'participant-activity-review.json',
                'participant_review_sha256': sha(attempt / 'participant-activity-review.json'),
                'designation_review_path': 'stand-designation-review.json',
                'designation_review_sha256': sha(attempt / 'stand-designation-review.json'),
                'other_regulations_review_path': 'other-regulations-review.json',
                'other_regulations_review_sha256': sha(attempt / 'other-regulations-review.json')}})
    result = measure(measured_rows, 'original_native')
    result['source_kind'] = 'synthetic_cpu_fixture' if any(
        json.loads((attempt / name).read_text()).get('synthetic_cpu_fixture') is True
        for name in MEASUREMENT_INPUTS[1:]) else 'reviewed_saved_sources'
    result.pop('legal_verdict', None)
    return result


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved attempt')
    for name in (*SOURCE_INPUTS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id')
    if (case != construction.get('case_id') or
            case not in {config.get('assignment_id', '') + '__probe_a',
                         config.get('assignment_id', '') + '__probe_b'}):
        raise ValueError('Selected taxi case identity differs')
    measurement = taxi_loading_measurement(attempt)
    expected = ('passenger_loading' if case.endswith('__probe_a') else
                'merchandise_loading')
    if measurement['requested_activity'] != expected:
        raise ValueError('Observed activity differs from selected taxi case')
    sources = {name: sha(attempt / name) for name in MEASUREMENT_INPUTS}
    description = construction['recording_description']
    designation = json.loads((attempt / 'stand-designation-review.json').read_text())
    sign_observation = designation.get('observed_sign_content')
    if not sign_observation:
        raise ValueError('Original stand sign observation missing')
    evidence = []
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=False)
    for channel in description['channels']:
        name = channel['name']
        reference = 'channels/' + name + '.jsonl'
        with (attempt / reference).open('x') as stream:
            for row in rows(attempt / 'observed-activity.jsonl'):
                stream.write(json.dumps({'time_s': row['time_s'],
                    'value': row.get('observed_door_open') if name == 'sig.door_open'
                    else row.get('observed_occupant_count') if name == 'ru.occupant_count'
                    else row.get('observed_speed_mps') if name in ('drv.stopped', 'drv.standing_or_parked')
                    else row['time_s'] if name == 'kin.time'
                    else row.get('observed_stand_location') if name in ('st.curb_zone', 'rel.occupies')
                    else sign_observation if name == 'dev.regulatory_sign'
                    else row.get('observed_taxi_identity')}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': reference})
    context_dir = attempt / 'context'
    context_dir.mkdir(exist_ok=True)
    context_sources = {
        'taxi_license_review': 'taxi-license-review.json',
        'stand_designation_review': 'stand-designation-review.json',
        'other_regulations_review': 'other-regulations-review.json'}
    for context in description['context_inputs']:
        name = context['name']
        source = json.loads((attempt / context_sources[name]).read_text())
        reference = 'context/' + name + '.json'
        expected_context = json.dumps({
            name: {'source_basis': source['source_basis'],
                   'source_sha256': sha(attempt / context_sources[name]),
                   'review_status': source.get('review_status')},
            'source_kind': 'synthetic_cpu_fixture' if source.get('synthetic_cpu_fixture')
            else 'reviewed_original_source'}, allow_nan=False) + '\n'
        context_path = attempt / reference
        if context_path.is_file():
            if context_path.read_text() != expected_context:
                raise ValueError('Existing context observation differs from original review')
        else:
            context_path.write_text(expected_context)
        evidence.append({'name': name, 'unit': context['unit'],
                         'reference': reference})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'taxi_loading_measurement': {
                  'method': 'taxi_loading_measurement', 'value': measurement,
                  'sources': sources}}, 'source_complete': True,
              'physical_or_legal_acceptance': False}
    result = {'case_id': case, 'measured_values': measurement,
              'target_checks': [{'target': 'source-observed taxi loading activity',
                  'requested': expected, 'measured': measurement['requested_activity'],
                  'method': 'taxi_loading_measurement', 'tolerance': 0,
                  'matched': True, 'physical_cause_confirmed': False,
                  'cause_evidence': list(sources)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved taxi sources measured; original authority and physical review pending',
              'physical_failure_flags': ['Original stand authority and camera pixels require review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if measurement['source_kind'] == 'synthetic_cpu_fixture' else 'original_source_review',
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

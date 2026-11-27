"""Finalize same-lane motorcycle sources without treating a request as evidence."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_follow import measure as measure_follow
from measure_pass import measure as measure_pass
from law_review import review as review_law

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'pass-context.json', 'participant-poses.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           *(view + '.mkv' for view in VIEWS))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def measure_same_lane_episode(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    if config['selected_case_id'].endswith('__controlled_1'):
        return measure_follow(root)
    if config['selected_case_id'].endswith('__controlled_2'):
        return measure_pass(root)
    raise ValueError('Unknown exact same-lane case')


def measure_statutory_alternatives(root):
    root = Path(root)
    config = json.loads((root / 'config.json').read_text())
    context = json.loads((root / 'pass-context.json').read_text())
    action = 'following' if config['selected_case_id'].endswith('__controlled_1') else 'pass'
    return review_law({'rider_class': context['rider_class'],
                       'other_class': context['passed_class'],
                       'observed_action': action,
                       'classification_source': context['classification_source'],
                       'driver_consent': None}, root)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists(),
            'Fresh saved-only motorcycle finalization required')
    for name in ('config.json', 'construction.json', 'pass-review.json', *SOURCES):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id')
    require(case == construction.get('case_id') and
            case in config.get('supported_case_ids', []), 'Exact selected case changed')
    review = json.loads((attempt / 'pass-review.json').read_text())
    require(review.get('case_id') == case and
            review.get('assignment_id') == case.rsplit('__', 1)[0],
            'Original motorcycle source review identity differs')
    require(review.get('review_kind') in ('original_native_source', 'synthetic_diagnostic'),
            'Original or declared synthetic source review required')
    for name in SOURCES:
        if review['review_kind'] == 'synthetic_diagnostic' and name.endswith('.mkv'):
            continue
        require(review.get('source_sha256', {}).get(name) == sha(attempt / name),
                'Reviewed motorcycle source hash differs: ' + name)
    poses = rows(attempt / 'participant-poses.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    require(len(poses) == len(frames) == len(trace) == 600,
            'Full original motorcycle frame span missing')
    for i, (pose, frame, core) in enumerate(zip(poses, frames, trace)):
        native = pose.get('native_frame')
        require(pose.get('video_frame') == frame.get('video_frame') == i and
                frame.get('native_frame') == core.get('frame') == native and
                abs(pose.get('time_s', -10) - frame.get('time_s', -20)) < .005 and
                abs(core.get('time_s', -30) - pose.get('time_s', -10)) < .005,
                'Original motorcycle Core/frame/time join differs')
        require(frame.get('camera_native_frames') == {view: native for view in VIEWS},
                'Four original camera frame joins differ')
        rider = pose['rider_body_xy_m']
        require(len(core.get('position_m', [])) == 3 and
                abs(core['position_m'][0] - sum(p[0] for p in rider) / 4) < .25,
                'Original motorcycle Core position differs from body')
    measured = measure_same_lane_episode(attempt)
    context = json.loads((attempt / 'pass-context.json').read_text())
    law = measure_statutory_alternatives(attempt)
    require(law['subsection_3_pair_eligible'] is False,
            'Car comparison unexpectedly entered two-rider exception')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    for spec in config['recording_description']['channels']:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for pose in poses:
                value = {'rider_actor_id': pose.get('rider_actor_id'),
                         'other_actor_id': pose.get('motor_actor_id'),
                         'rider_body_xy_m': pose['rider_body_xy_m'],
                         'other_body_xy_m': pose['motor_body_xy_m'],
                         'rider_blueprint_id': pose.get('rider_blueprint_id'),
                         'other_blueprint_id': pose.get('motor_blueprint_id'),
                         'rider_class': context['rider_class'],
                         'other_class': context['passed_class'],
                         'law_observation': law,
                         'source_measurement_only': True}
                stream.write(json.dumps({'time_s': pose['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': spec['unit'],
                         'reference': 'channels/' + path.name})
    hashes = {name: sha(attempt / name) for name in SOURCES}
    hashes['pass-review.json'] = sha(attempt / 'pass-review.json')
    report = {'format': 'worker-analysis-report-v1', 'case_id': case,
              'measurements': {'same_lane_episode': {
                  'method': 'measure_same_lane_episode', 'value': measured,
                  'sources': hashes},
                  'statutory_alternatives': {
                      'method': 'measure_statutory_alternatives', 'value': law,
                      'sources': {name: hashes[name] for name in
                                  ('pass-context.json', 'participant-poses.jsonl',
                                   'pass-review.json')}}},
              'statutory_alternative_review': law,
              'legal_verdict_claimed': False,
              'physical_acceptance_claimed': False}
    if case.endswith('__controlled_1'):
        requested = 'same-lane following without overlap'
        matched = measured['longitudinal_overlap_frames'] == 0
    else:
        requested = 'complete same-lane behind-to-ahead pass'
        matched = measured['first_behind_frame'] < measured['first_overlap_frame'] < measured['first_clear_ahead_frame']
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': requested, 'requested': True,
                                 'measured': matched,
                                 'method': 'Original post-tick full-body source sequence',
                                 'tolerance': 0,
                                 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(hashes)}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'full 600-frame source diagnostic',
              'physical_failure_flags': ['Original Native body clearance and visible classification require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence + [
                  {'name': 'motorcycle_class', 'unit': 'category', 'reference': 'pass-context.json'},
                  {'name': 'subsection_3_exception', 'unit': 'source text', 'reference': 'pass-context.json'}],
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if
              review['review_kind'] == 'synthetic_diagnostic' else 'original_native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))

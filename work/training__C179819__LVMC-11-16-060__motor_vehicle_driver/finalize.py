"""Recorded-only speed measurement; no legal or physical acceptance claim."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_speed import measure


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def speed_and_governance_measurement(root):
    root = Path(root)
    road = required(root, 'road.xodr')
    survey_path = required(root, 'sign-survey.json')
    status_path = required(root, 'street-status.json')
    trace_path = required(root, 'actor-poses.jsonl')
    survey = json.loads(survey_path.read_text())
    status = json.loads(status_path.read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected_review = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed'
    if status.get('source_kind') != 'independent_street_status' or status.get('review_status') != expected_review:
        raise ValueError('Independent street or highway status source required')
    if not status.get('reviewer'):
        raise ValueError('Street status source lacks reviewer')
    if status.get('road_sha256') != sha(road):
        raise ValueError('Street status source differs from original road')
    if survey.get('source_kind') != 'native_complete_sign_survey' or survey.get('review_status') != expected_review:
        raise ValueError('Independent complete sign survey required')
    if not survey.get('reviewer'):
        raise ValueError('Sign survey source lacks reviewer')
    if survey.get('road_sha256') != sha(road):
        raise ValueError('Sign survey source differs from original road')
    signs = survey.get('applicable_posted_signs')
    if signs:
        if survey.get('pixel_source') != 'reference_corner.mkv':
            raise ValueError('Original sign pixel source required')
        video_sha = sha(required(root, 'reference_corner.mkv'))
        if any(sign.get('pixel_sha256') != video_sha for sign in signs):
            raise ValueError('Sign review differs from original source pixels')
    context = {'source_kind': 'native_speed_and_complete_sign_survey',
               'native_map_sha256': sha(road), 'street_status_sha256': sha(status_path),
               'sign_survey_sha256': sha(survey_path),
               'street_status': status.get('street_status'),
               'surveyed_route_interval_m': survey.get('surveyed_route_interval_m'),
               'survey_complete_both_directions': survey.get('survey_complete_both_directions'),
               'applicable_posted_signs': survey.get('applicable_posted_signs')}
    rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
    return measure(context, rows)


def prima_facie_context(root):
    source = json.loads(required(root, 'law-text.json').read_text())
    if source.get('text') != ('The prima facie speed limit is twenty-five miles per hour on all streets '
                              'and highways unless a different speed limit is posted as set forth in this Title.'):
        raise ValueError('Exact statutory text source changed')
    return {'phrase': 'prima facie', 'status': 'legal_interpretation_reserved',
            'speed_and_governance_are_measurements_only': True}


def report(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    value = speed_and_governance_measurement(root)
    names = ('road.xodr', 'sign-survey.json', 'street-status.json',
             'actor-poses.jsonl', 'reference_corner.mkv')
    return {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
            'measurements': {'source_bound_speed_and_governance': {
                'method': 'speed_and_governance_measurement', 'value': value,
                'sources': {name: sha(required(root, name)) for name in names}},
                'prima_facie_context': {'method': 'prima_facie_context',
                    'value': prima_facie_context(root),
                    'sources': {'law-text.json': sha(required(root, 'law-text.json'))}}},
            'scope': 'original speed and independently reviewed street/sign context; legal outcome unassessed'}


def derive_channels(root, config):
    root = Path(root)
    rows = [json.loads(line) for line in required(root, 'actor-poses.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in required(root, 'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != 600 or len(mapping) != 600:
        raise ValueError('Complete original 600-frame source joins required')
    names = {entry['name'] for entry in config['recording_description']['channels']}
    expected = {'kin.speed', 'dev.speed_limit_sign', 'dev.governs', 'st.roadway', 'rel.occupies'}
    if names != expected:
        raise ValueError('Declared source channels differ from finalizer')
    survey = json.loads(required(root, 'sign-survey.json').read_text())
    street = json.loads(required(root, 'street-status.json').read_text())
    channels = {name: [] for name in expected}
    for i, (pose, frame) in enumerate(zip(rows, mapping)):
        if pose['video_frame'] != i or pose['native_frame'] != frame['native_frame'] or abs(pose['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Original pose/frame identity differs')
        position = pose['route_position_m']
        applicable = [sign for sign in survey['applicable_posted_signs']
                      if sign['governs_from_m'] <= position < sign['governs_to_m']]
        if len(applicable) > 1:
            raise ValueError('Conflicting posted signs at original position')
        values = {'kin.speed': pose['observed_speed_mps'],
                  'dev.speed_limit_sign': {'applicable': applicable, 'survey_sha256': sha(root / 'sign-survey.json')},
                  'dev.governs': {'route_position_m': position, 'posted_limit_mph': applicable[0]['limit_mph'] if applicable else None},
                  'st.roadway': {'street_status': street['street_status'], 'road_sha256': sha(root / 'road.xodr')},
                  'rel.occupies': {'route_position_m': position, 'street_status_sha256': sha(root / 'street-status.json')}}
        for name, value in values.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    directory = root / 'channels'
    directory.mkdir(exist_ok=True)
    for name, values in channels.items():
        (directory / (name + '.jsonl')).write_text(''.join(json.dumps(value, allow_nan=False) + '\n' for value in values))


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh stage')
    config = json.loads(required(root, 'config.json').read_text())
    analysis = report(root)
    derive_channels(root, config)
    measured = analysis['measurements']['source_bound_speed_and_governance']['value']
    target_mph = {'slow': 20, 'at_default': 25, 'fast': 30, 'posted_35': 30}[config['speed_case']]
    actual_range = measured['observed_speed_mph_range']
    target = {'target': 'original observed speed over surveyed route',
              'requested': target_mph, 'measured': actual_range,
              'method': 'saved original Native velocity magnitude, all 600 frames',
              'tolerance': 2, 'matched': actual_range[0] <= target_mph + 2 and actual_range[1] >= target_mph - 2,
              'physical_cause_confirmed': False, 'cause_evidence': ['actor-poses.jsonl']}
    evidence = [{'name': name, 'unit': 'source', 'reference': name} for name in
                ('road.xodr', 'street-status.json', 'sign-survey.json', 'actor-poses.jsonl')]
    evidence += [{'name': row['name'], 'unit': row['unit'], 'reference': row['source']}
                 for row in config['recording_description']['channels']]
    result = {'case_id': config['case_id'],
              'measured_values': measured, 'target_checks': [target],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Awaiting source-bound physical review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              **provenance_record(root), 'accepted': False, 'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    write_result(root, result)
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)


if __name__ == '__main__':
    main()

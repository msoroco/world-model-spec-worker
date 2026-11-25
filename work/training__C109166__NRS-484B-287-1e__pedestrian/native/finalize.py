"""Recorded-only diagonal source measurement; no legal or pixel verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from native_request import camera_plan, authorize_native_capture
from original_source_audit import audit


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def diagonal_entry_measurement(attempt):
    attempt = Path(attempt)
    files = ('video_frames.jsonl', 'pedestrian-original.jsonl',
             'device-original.jsonl', 'camera-sources.jsonl')
    hashes = {name: sha(required(attempt, name)) for name in files}
    receipt = json.loads(required(attempt, 'authority-receipt.json').read_text())
    for source in receipt.values():
        required(attempt, source['path'])
    structural = audit(attempt, hashes, receipt)
    return {'first_entry_frame': structural['first_entry_video_frame'],
            'first_entry_native_frame': structural['first_entry_native_frame'],
            'first_entry_instruction': structural['first_entry_device_instruction'],
            'duration_s': structural['duration_s'],
            'authority_review_pending': True,
            'road_boundary_review_pending': True,
            'actual_pixels_review_pending': True,
            'legal_verdict': None}


def exception_applicability_measurement(attempt):
    """Record the independent review source; leave legal applicability to a reviewer."""
    attempt = Path(attempt)
    source = json.loads(required(attempt, 'exception-applicability-source.json').read_text())
    if source.get('format') != 'c109166-exception-applicability-source-v1' or source.get('statute') != 'NRS 484B.290':
        raise ValueError('Exact NRS 484B.290 exception source required')
    if source.get('review_status') not in ('pending_independent_review', 'independently_reviewed'):
        raise ValueError('Exception review status invalid')
    if source['review_status'] == 'independently_reviewed':
        statute_path = source.get('exact_statute_source_path', '')
        person_path = source.get('person_specific_evidence_path', '')
        if (not source.get('independent_reviewer') or
                source.get('applicability') not in ('applicable', 'not_applicable', 'undetermined') or
                not statute_path or Path(statute_path).is_absolute() or '..' in Path(statute_path).parts or
                not person_path or Path(person_path).is_absolute() or '..' in Path(person_path).parts or
                source.get('exact_statute_source_sha256') != sha(required(attempt, statute_path)) or
                source.get('pedestrian_original_sha256') != sha(required(attempt, 'pedestrian-original.jsonl')) or
                source.get('person_specific_evidence_sha256') != sha(required(attempt, person_path))):
            raise ValueError('Independent person-specific NRS 484B.290 review incomplete')
    return {'statute': 'NRS 484B.290', 'review_status': source['review_status'],
            'applicability': source.get('applicability', 'undetermined'),
            'legal_verdict': None}


def report(attempt, case_id):
    attempt = Path(attempt)
    value = diagonal_entry_measurement(attempt)
    sources = {name: sha(required(attempt, name)) for name in
               ('pedestrian-original.jsonl', 'device-original.jsonl', 'authority-receipt.json')}
    exception = exception_applicability_measurement(attempt)
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'diagonal_first_entry_instruction': {
                'method': 'diagonal_entry_measurement', 'value': value, 'sources': sources},
                'nrs_484b_290_exception_context': {
                'method': 'exception_applicability_measurement', 'value': exception,
                'sources': {'exception-applicability-source.json': sha(required(attempt, 'exception-applicability-source.json'))}}},
            'scope': 'source-bound original Native first entry; authority, actual pixels and legal judgment pending'}


def derive_channels(attempt, config):
    people = [json.loads(s) for s in required(attempt, 'pedestrian-original.jsonl').read_text().splitlines()]
    devices = [json.loads(s) for s in required(attempt, 'device-original.jsonl').read_text().splitlines()]
    mapping = [json.loads(s) for s in required(attempt, 'video_frames.jsonl').read_text().splitlines()]
    if not len(people) == len(devices) == len(mapping) == 600:
        raise ValueError('complete original channel inputs required')
    channels = {entry['name']: [] for entry in config['recording_description']['channels']}
    length = 0.0
    previous = None
    for person, device, frame in zip(people, devices, mapping):
        center = person['center_xy_m']
        if previous is not None:
            length += math.dist(previous, center)
        previous = center
        time = frame['time_s']
        values = {
            'ru.subject': person['walker_id'],
            'ru.pedestrian': {'native_actor_id': person['walker_id']},
            'dev.pedestrian_signal': {'device_id': device['device_id'],
                                      'native_state': device['displayed_instruction'],
                                      'original_pixels_review_pending': True},
            'dev.regulatory_sign': {'authority_source': 'authority-receipt.json',
                                    'original_sign_review_pending': True},
            'dev.governs': {'movement_id': 'c109166-diagonal-sw-ne',
                            'independent_review_pending': True},
            'st.intersection': {'entry_boundary_review_pending': True},
            'kin.position': center,
            'kin.heading': [2 ** -.5, 2 ** -.5],
            'kin.path_length': length,
            'kin.time': time,
            'rel.occupies': {'original_footprint_xy_m': person['footprint_xy_m'],
                             'road_boundary_review_pending': True},
        }
        if set(channels) != set(values):
            raise ValueError('declared original channels differ from finalizer')
        for name, value in values.items():
            channels[name].append({'time_s': time, 'value': value})
    directory = attempt / 'channels'
    directory.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (directory / (name + '.jsonl')).write_text(
            ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def reviewed_physical_status(attempt, measured):
    """Use saved original joins plus independent review; never infer from a label."""
    sources = {name: sha(required(attempt, name)) for name in
               ('video_frames.jsonl', 'pedestrian-original.jsonl', 'device-original.jsonl')}
    review_path = attempt / 'road-boundary-review.json'
    pixel_path = attempt / 'diagonal-pixel-review.json'
    if review_path.is_file() != pixel_path.is_file():
        raise ValueError('paired independent boundary and pixel reviews required')
    source_status = 'unverified'
    maneuver_status = 'unverified'
    reason = 'independent original boundary and pixel review absent'
    if review_path.is_file() and pixel_path.is_file():
        config = json.loads(required(attempt, 'config.json').read_text())
        authorize_native_capture(attempt,
                                 json.loads(required(attempt, 'authority-receipt.json').read_text()),
                                 config['opendrive_signal_id'])
        boundary = json.loads(review_path.read_text())
        pixels = json.loads(pixel_path.read_text())
        if (boundary.get('review_status') != 'independently_reviewed' or
                not boundary.get('independent_reviewer') or
                boundary.get('source_sha256') != sources or
                boundary.get('first_entry_native_frame') != measured['first_entry_native_frame'] or
                pixels.get('review_status') != 'independently_reviewed' or
                not pixels.get('independent_reviewer') or
                pixels.get('frame_map_sha256') != sources['video_frames.jsonl'] or
                pixels.get('first_entry_native_frame') != measured['first_entry_native_frame'] or
                pixels.get('actual_diagonal_instruction') != measured['first_entry_instruction']):
            raise ValueError('independent original boundary/pixel review differs from saved source')
        videos = {name: sha(required(attempt, name + '.mkv')) for name in
                  ('overview', 'approach', 'reference_corner', 'driver_reference')}
        if pixels.get('source_video_sha256') != videos:
            raise ValueError('independent original pixel review video hashes differ')
        source_status = 'met'
        if (boundary.get('full_body_diagonal_clearance_observed') is True and
                boundary.get('authorized_diagonal_path_observed') is True and
                type(boundary.get('clearance_native_frame')) is int and
                boundary['clearance_native_frame'] > measured['first_entry_native_frame']):
            maneuver_status = 'met'
            reason = 'independently reviewed original full-body diagonal clearance'
        else:
            maneuver_status = 'not_met'
            reason = 'reviewed original source does not establish complete diagonal clearance'
        sources['road-boundary-review.json'] = sha(review_path)
        sources['diagonal-pixel-review.json'] = sha(pixel_path)
    check = lambda status: {'status': status,
                            'method': 'independently reviewed original pedestrian body, boundary and device pixels',
                            'sources': sources, 'intervals': [], 'reason': reason,
                            'legal_verdict_claimed': False}
    return {'setup': check(source_status), 'target': check(source_status),
            'maneuver': check(maneuver_status)}


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result, provenance_record
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh stage')
    config = json.loads(required(attempt, 'config.json').read_text())
    case = config['case_id']
    analysis = report(attempt, case)
    derive_channels(attempt, config)
    authority_context = {'diagonal_authority_source': {
        'receipt_sha256': sha(required(attempt, 'authority-receipt.json')),
        'independent_review_pending': True}}
    (attempt / 'diagonal-authority-context.json').write_text(
        json.dumps(authority_context, indent=2, allow_nan=False) + '\n')
    measured = analysis['measurements']['diagonal_first_entry_instruction']['value']
    physical_checks = reviewed_physical_status(attempt, measured)
    measured['road_boundary_review_pending'] = physical_checks['maneuver']['status'] == 'unverified'
    measured['actual_pixels_review_pending'] = physical_checks['target']['status'] == 'unverified'
    expected = 'diagonal_walk' if config['case_suffix'] == 'controlled_1' else 'diagonal_dont_walk'
    evidence = [{'name': name, 'unit': 'source', 'reference': name}
                for name in ('pedestrian-original.jsonl', 'device-original.jsonl',
                             'camera-sources.jsonl', 'authority-receipt.json',
                             'exception-applicability-source.json')]
    for channel in config['recording_description']['channels']:
        evidence.append({'name': channel['name'], 'unit': channel['unit'],
                         'reference': channel['source']})
    evidence.append({'name': 'diagonal_authority_source', 'unit': 'source',
                     'reference': 'diagonal-authority-context.json'})
    result = {'case_id': case,
              'measured_values': {'first_entry_instruction': measured['first_entry_instruction'],
                                  'first_entry_native_frame': measured['first_entry_native_frame']},
              'target_checks': [{'target': 'original first-entry diagonal device instruction',
                  'requested': expected, 'measured': measured['first_entry_instruction'],
                  'method': 'saved original device and pedestrian frame join', 'tolerance': 0,
                  'matched': measured['first_entry_instruction'] == expected,
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['pedestrian-original.jsonl', 'device-original.jsonl']}],
              'setup_confirmed': physical_checks['setup']['status'] == 'met',
              'behavior_attempted': True,
              'maneuver_completed': physical_checks['maneuver']['status'] == 'met',
              'physical_checks': physical_checks,
              'termination_reason': physical_checks['maneuver']['reason'],
              'physical_failure_flags': [] if physical_checks['maneuver']['status'] == 'met' else
                  [physical_checks['maneuver']['reason']],
              'trace_reference': 'trace.jsonl',
              'video_references': [item['name'] + '.mkv' for item in camera_plan()],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {},
              **provenance_record(attempt),
              'accepted': False, 'legal_verdict_claimed': False}
    validate_result(result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempt = Path(args.attempt)
    config = json.loads(required(attempt, 'config.json').read_text())
    analysis = finalize(attempt, args.output)
    print(json.dumps({'case_id': analysis['case_id'], 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()

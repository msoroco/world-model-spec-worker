"""Recorded-only diagonal source measurement; no legal or pixel verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from native_request import camera_plan
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


def report(attempt, case_id):
    attempt = Path(attempt)
    value = diagonal_entry_measurement(attempt)
    sources = {name: sha(required(attempt, name)) for name in
               ('pedestrian-original.jsonl', 'device-original.jsonl', 'authority-receipt.json')}
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'diagonal_first_entry_instruction': {
                'method': 'diagonal_entry_measurement', 'value': value, 'sources': sources}},
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


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh stage')
    config = json.loads(required(attempt, 'config.json').read_text())
    case = config['case_id']
    analysis = report(attempt, case)
    derive_channels(attempt, config)
    measured = analysis['measurements']['diagonal_first_entry_instruction']['value']
    expected = 'diagonal_walk' if config['case_suffix'] == 'controlled_1' else 'diagonal_dont_walk'
    evidence = [{'name': name, 'unit': 'source', 'reference': name}
                for name in ('pedestrian-original.jsonl', 'device-original.jsonl',
                             'camera-sources.jsonl', 'authority-receipt.json')]
    for channel in config['recording_description']['channels']:
        evidence.append({'name': channel['name'], 'unit': channel['unit'],
                         'reference': channel['source']})
    result = {'case_id': case,
              'measured_values': {'first_entry_instruction': measured['first_entry_instruction'],
                                  'first_entry_native_frame': measured['first_entry_native_frame']},
              'target_checks': [{'target': 'original first-entry diagonal device instruction',
                  'requested': expected, 'measured': measured['first_entry_instruction'],
                  'method': 'saved original device and pedestrian frame join', 'tolerance': 0,
                  'matched': measured['first_entry_instruction'] == expected,
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['pedestrian-original.jsonl', 'device-original.jsonl']}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False,
              'termination_reason': 'saved structural and pixel review pending',
              'physical_failure_flags': ['official diagonal authority, road boundary and pixels unreviewed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [item['name'] + '.mkv' for item in camera_plan()],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'diagonal_first_entry_instruction': {
                  'value': measured['first_entry_instruction'], 'unit': 'instruction',
                  'method': 'original Native device readback joined to first entry proxy',
                  'time_window': 'complete 30-second original capture',
                  'statistic': 'first entry proxy frame', 'reference': 'device-original.jsonl'}},
              'provenance_kind': 'native_source_shape_unverified',
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

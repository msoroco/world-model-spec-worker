"""Saved-only flagger, area, signal and driver-response measurements."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

from flagger_zone import CASES, SOURCES, measure_original
from source_packet import ASSIGNMENT, verify


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, output):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    construction = json.loads(required(root, 'construction.json').read_text())
    case_id = config['selected_case_id']
    if construction['case_id'] != case_id or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('exact selected flagger construction differs')
    case = next((item for item in CASES if case_id == ASSIGNMENT + '__' + item.name), None)
    if case is None:
        raise ValueError('unknown exact selected flagger case')
    diagnostic = (root / 'fixture-provenance.json').is_file()
    source_dir = root / 'original-flagger-source'
    packet_path = required(source_dir, 'source-packet.json')
    verified = verify(packet_path, diagnostic_fixture=diagnostic)
    if verified['case_id'] != case_id:
        raise ValueError('exact original flagger source case differs')
    packet = json.loads(packet_path.read_text())
    ticks_path = required(source_dir, 'original-ticks.jsonl')
    ticks = load_rows(ticks_path)
    expected = 9 if diagnostic else 900
    if len(ticks) != expected:
        raise ValueError('original flagger frame count incomplete')
    if not diagnostic:
        from capture_seal import seal
        seal(source_dir)
    measured = measure_original(ticks, packet['scene'], case, expected_frames=expected)
    trace = load_rows(required(root, 'trace.jsonl'))
    mapping = load_rows(required(root, 'video_frames.jsonl'))
    if len(trace) != expected or len(mapping) != expected:
        raise ValueError('original Native trace or video mapping incomplete')
    for index, (row, frame, video) in enumerate(zip(ticks, trace, mapping)):
        if frame.get('frame') != row['original_frame'] or \
                abs(frame.get('time_s', -1000) - row['time_s']) > .005 or \
                video.get('native_frame') != row['original_frame'] or \
                video.get('video_frame') != index:
            raise ValueError('original flagger source/frame/video join differs')
    hashes = {'source-packet.json': sha(packet_path),
              'original-ticks.jsonl': sha(ticks_path),
              'trace.jsonl': sha(root / 'trace.jsonl'),
              'video_frames.jsonl': sha(root / 'video_frames.jsonl')}
    for name in SOURCES:
        ref = packet['source_refs'][name]
        hashes['source:' + name] = ref['sha256']
    values = {'case_id': case_id, 'source_frame_count': expected,
              'area_designated': case.designated,
              'marked_construction': case.marked_construction,
              'flagger_authorized': case.authorized,
              'signal_content': case.signal,
              'driver_response_request': case.response,
              'observed_active_speed_mps': measured['maximum_active_speed_mps'],
              'active_signal_frames': measured['active_signal_frames'],
              'legal_failure_or_refusal': None}
    measurements = {
        'qualifying_driver_highway': {'driver_id': packet['scene']['driver_id'],
                                     'vehicle_id': packet['scene']['vehicle_id'],
                                     'highway': packet['scene']['highway']},
        'flagger_authority_and_role': {'flagger_id': packet['scene']['flagger_id'],
                                      'authorized': case.authorized,
                                      'source_sha256': hashes['source:flagger_authorization']},
        'clearly_marked_construction': {'marked': case.marked_construction,
                                        'construction_source_sha256': hashes['source:construction_or_maintenance'],
                                        'marking_source_sha256': hashes['source:construction_marking']},
        'designated_temporary_zone': {'designated': case.designated,
                                      'zone_source_sha256': hashes['source:zone_designation']},
        'applicable_flagger_signal': {'content': case.signal,
                                      'recipient': packet['scene']['vehicle_id'],
                                      'source_sha256': hashes['source:signal_content']},
        'original_driver_response': {'maximum_active_speed_mps': measured['maximum_active_speed_mps'],
                                     'active_signal_frames': measured['active_signal_frames'],
                                     'legal_failure_or_refusal': None}}
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {name: {'method': 'measure', 'value': value,
                                      'sources': hashes}
                               for name, value in measurements.items()},
              'diagnostic_fixture': diagnostic,
              'legal_verdict_claimed': False,
              'limitations': ['Physical signal visibility and actual response require original Native review.',
                              'A diagnostic fixture cannot establish zone designation or flagger authorization.']}
    channels = root / 'channels'
    channels.mkdir(exist_ok=False)
    channel_values = {
        'original_vehicle_motion': {'source_sha256': hashes['original-ticks.jsonl'],
                                    'maximum_active_speed_mps': measured['maximum_active_speed_mps']},
        'flagger_signal': {'source_sha256': hashes['source-packet.json'],
                           'signal': case.signal, 'recipient': packet['scene']['vehicle_id']},
        'camera_pixels': {'source_sha256': hashes['video_frames.jsonl'],
                           'views': ['overview', 'approach', 'reference_corner', 'driver_reference']}}
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('unexpected flagger recording channel: ' + name)
        target = channels / (name + '.jsonl')
        target.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                               'value': channel_values[name]}, sort_keys=True) + '\n'
                                  for row in trace))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': str(target.relative_to(root))})
    result = {'case_id': case_id, 'measured_values': values,
              'target_checks': [{'target': 'source-bound flagger authority, area, signal and response',
                                 'requested': case_id, 'measured': values,
                                 'method': 'flagger_zone.measure_original',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Saved original flagger review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'legal_judgment': None, 'physical_acceptance_claimed': False}
    (root / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    Path(output).write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(analyze(args.attempt, args.output)['case_id'])


if __name__ == '__main__':
    main()

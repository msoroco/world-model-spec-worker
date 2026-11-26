"""Source-bound saved designated-place finalization; no legal verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from build_saved_packet import build, packet_from_attempt
from physical_check import assess

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv',
          'driver_reference.mkv')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def designated_place_observation(attempt):
    return build(attempt)


def person_activity_context(attempt):
    return {'person_activity': json.loads(required(attempt, 'person-activity.json').read_text()),
            'traffic_direction': json.loads(required(attempt, 'traffic-direction.json').read_text())}


def decoded_frames(path):
    call = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if call.returncode or not call.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + path.name)
    return int(call.stdout.strip())


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Choose fresh saved analysis output')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('frames') != 600:
        raise ValueError('Original designated-stop frame contract differs')
    packet = packet_from_attempt(attempt)
    measured = designated_place_observation(attempt)
    physical = assess(packet)
    person = person_activity_context(attempt)
    mapping = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    native = packet['rows']
    evidence = rows(required(attempt, 'capture/evidence.jsonl'))
    if any(len(item) != 600 for item in (mapping, trace, native, evidence)):
        raise ValueError('Original designated-stop source frame count differs')
    for index, (frame, core, body, scene) in enumerate(zip(mapping, trace, native, evidence)):
        if frame.get('video_frame') != index or body.get('video_frame') != index or \
                frame.get('native_frame') != body.get('native_frame') or \
                core.get('frame') != body.get('native_frame') or \
                scene.get('original_frame') != body.get('native_frame') or \
                abs(core.get('speed_mps', -100) - body.get('observed_speed_mps', -200)) > 1e-4 or \
                any(abs(a - b) > 1e-4 for a, b in
                    zip(core.get('position_m', []), body.get('position_m', []))) or \
                len(core.get('position_m', [])) != 3:
            raise ValueError('Original body/Core/evidence/video frame join differs')
    counts = {name: decoded_frames(required(attempt, name)) for name in VIDEOS}
    if set(counts.values()) != {600}:
        raise ValueError('Original four-view source video count differs')
    provenance = provenance_record(attempt)
    original = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    channel = attempt / 'channels/designated_place.jsonl'
    channel.parent.mkdir(exist_ok=True)
    channel.write_text('\n'.join(json.dumps({'time_s': row['time_s'],
        'value': {'observed_speed_mps': row['observed_speed_mps'],
                  'vehicle_footprint_map_m': row['vehicle_footprint_map_m']}})
        for row in native) + '\n')
    context = attempt / 'channels/person_activity_context.json'
    context.write_text(json.dumps({'person_activity_context': person}, indent=2, allow_nan=False) + '\n')
    result = {'case_id': config['case_id'],
        'measured_values': {'designated_place': measured, 'physical': physical,
                            'person_activity_context': person},
        'target_checks': [{'target': 'sourced_destination_rest',
            'requested': config['case']['comparison_condition'],
            'measured': physical['observation'],
            'method': 'original frame-linked body and position observation',
            'tolerance': 'engineering observation only; no legal threshold',
            'matched': physical['status'] == 'met',
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-stop-trace.jsonl', 'video_frames.jsonl']}],
        'setup_confirmed': original,
        'behavior_attempted': original,
        'maneuver_completed': original and physical['status'] == 'met',
        'termination_reason': '600 original source frames retained',
        'physical_failure_flags': [] if physical['status'] == 'met' else
                                  ['destination_rest_not_observed'],
        'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [
            {'name': 'designated_place', 'unit': 'structured',
             'reference': 'channels/designated_place.jsonl'},
            {'name': 'person_activity_context', 'unit': 'structured',
             'reference': 'channels/person_activity_context.json'}],
        'realized_observables': {
            'rest_and_body_overlap_frames': {'value': measured['rest_and_body_overlap_frames'],
                'unit': 'frames', 'method': 'source polygon intersection during observed rest',
                'time_window': '600 frames', 'statistic': 'count',
                'reference': 'native-stop-trace.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    sources = ('original-device.json', 'original-designation.json', 'original-map.json',
               'person-activity.json', 'traffic-direction.json',
               'native-stop-trace.jsonl', 'video_frames.jsonl',
               'trace.jsonl', 'capture/evidence.jsonl')
    hashes = {name: digest(required(attempt, name)) for name in sources}
    report = {'format': 'c229954-designated-stop-analysis-v1',
        'case_id': config['case_id'], 'analysis_complete': True,
        'legal_verdict_claimed': False,
        'measurements': {
            'designated_place_observation': {
                'method': 'designated_place_observation', 'value': measured,
                'sources': {name: hashes[name] for name in
                    ('original-device.json', 'original-designation.json',
                     'original-map.json', 'native-stop-trace.jsonl',
                     'video_frames.jsonl')}},
            'person_activity_context': {
                'method': 'person_activity_context', 'value': person,
                'sources': {name: hashes[name] for name in
                    ('person-activity.json', 'traffic-direction.json')}}},
        'physical_check': physical, 'source_hashes': hashes,
        'source_video_frames': counts, 'provenance': provenance,
        'limitations': ['Diagnostic fixtures do not establish original Native geometry or pixels.',
                        'Stop, stand, park and hazardous-place legal characterization require review.']}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))

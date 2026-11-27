"""Saved-only, source-bound red-curb measurement without a legal verdict."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from red_curb import CASES, measure_activity
from source_packet import ASSIGNMENT, CAMERAS, sha

SOURCES = ('original-red-curb-events.jsonl', 'red-curb-context.json',
           'camera-frame-map.jsonl', 'video_frames.jsonl', 'trace.jsonl')


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def lines(root, name):
    return [json.loads(line) for line in required(root, name).read_text(encoding='utf-8').splitlines()]


def verify_source_kind(root, case_id, expected_frames):
    seal = root / 'capture-seal.json'
    if seal.is_file():
        payload = json.loads(seal.read_text(encoding='utf-8'))
        if (payload.get('format') != 'worker-sealed-capture' or
                payload.get('provenance_kind') != 'native' or
                payload.get('diagnostic_fixture') is not False or
                payload.get('frames') != expected_frames or
                payload.get('restoration', {}).get('restored') is not True):
            raise ValueError('sealed original Native red-curb capture required')
        inventory = payload.get('sources')
        mandatory = set(SOURCES) | {name + '.mkv' for name in CAMERAS}
        mandatory.add('reviewed-sources/red-curb-packet.json')
        if not isinstance(inventory, dict) or not mandatory <= set(inventory):
            raise ValueError('original red-curb source inventory incomplete')
        for name, digest in inventory.items():
            if Path(name).is_absolute() or '..' in Path(name).parts or sha(required(root, name)) != digest:
                raise ValueError('sealed original source changed: ' + name)
        revision = payload.get('native_revision', {})
        if (revision.get('construction_sha256') != sha(required(root, 'construction.json')) or
                revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
            raise ValueError('sealed Native implementation changed')
        retained = json.loads(required(root, 'reviewed-sources/red-curb-packet.json').read_text())
        if retained.get('case_id') != case_id:
            raise ValueError('retained original packet case changed')
        return False
    note = json.loads(required(root, 'diagnostic-source-note.json').read_text())
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
            note.get('accepted_original_source') is not False or
            note.get('case_id') != case_id):
        raise ValueError('explicit synthetic red-curb diagnostic provenance required')
    return True


def measure_red_curb(measured, scene):
    return {'original_duration_s': measured['original_duration_s'],
            'vehicle_kind': measured['vehicle_kind'],
            'activity': measured['activity'],
            'purpose': measured['purpose'],
            'red_curb_source_sha256': scene['red_curb_source_sha256'],
            'sign_source_sha256': scene['sign_source_sha256'],
            'legal_judgment': None,
            'necessary_business_period_judgment': None,
            'expeditious_mail_deposit_judgment': None}


def analyze(root):
    root = Path(root).resolve()
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    case = next((item for item in CASES if ASSIGNMENT + '__' + item.name == case_id), None)
    if config.get('assignment_id') != ASSIGNMENT or case is None:
        raise ValueError('saved red-curb case identity differs')
    diagnostic = verify_source_kind(root, case_id, config['frame_count'])
    context = json.loads(required(root, 'red-curb-context.json').read_text())
    if context.get('format') != 'c229452-red-curb-context-v1' or context.get('case_id') != case_id:
        raise ValueError('original red-curb context differs')
    scene = context.get('scene')
    events = lines(root, 'original-red-curb-events.jsonl')
    cameras = lines(root, 'camera-frame-map.jsonl')
    frames = lines(root, 'video_frames.jsonl')
    trace = lines(root, 'trace.jsonl')
    expected = 9 if diagnostic else config['frame_count']
    if not all(len(part) == expected for part in (cameras, frames, trace)):
        raise ValueError('complete original or explicitly synthetic frame joins required')
    frame_times = {}
    for index, (camera, frame, graph) in enumerate(zip(cameras, frames, trace)):
        native = camera.get('native_frame')
        if (camera.get('frame_index') != index or
                camera.get('camera_frames') != {name: native for name in CAMERAS} or
                frame.get('video_frame') != index or frame.get('carla_frame') != native or
                frame.get('native_frame') != native or graph.get('frame') != native or
                abs(frame.get('time_s', -1) - camera.get('time_s', -2)) > .002):
            raise ValueError('original red-curb/frame/camera join differs')
        frame_times[native] = camera['time_s']
    for event in events:
        native = event.get('original_frame')
        if native not in frame_times:
            raise ValueError('original halt event not in captured frame map')
        if not diagnostic and abs(event.get('original_time_s', -1) - frame_times[native]) > .002:
            raise ValueError('original halt event time differs from captured frame')
    measured = measure_activity(events, scene, case)
    source_hashes = {name: sha(required(root, name)) for name in SOURCES}
    values = {
        'red_curb_location': {'painted': scene['red_curb_paint'],
                              'curb_segment_id': scene['curb_segment_id']},
        'sign_and_vehicle_status': {'sign': scene['sign'],
                                    'vehicle_kind': scene['vehicle_kind']},
        'original_halt_activity': measured,
        'exception_purpose': {'purpose': measured['purpose'],
                              'mail_dropbox_adjacent': scene['mail_dropbox_adjacent']},
        'attendance_and_engine': {'attended': measured['attended'],
                                  'engine_running': measured['engine_running']},
        'governing_context': {'traffic_conflict': measured['traffic_conflict'],
                              'police_direction': measured['police_direction'],
                              'device_direction': measured['device_direction']},
        'camera_frame_identity': {'frames': len(frames),
                                  'first_native_frame': frames[0]['native_frame'],
                                  'last_native_frame': frames[-1]['native_frame']},
    }
    evidence = []
    description = config['case']['recording_description']
    event_frames = {event['original_frame'] for event in events}
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown red-curb recording channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        stream = []
        for camera in cameras:
            value = dict(values[name])
            if name == 'original_halt_activity':
                value['event_at_original_frame'] = camera['native_frame'] in event_frames
            if name == 'camera_frame_identity':
                value['native_frame'] = camera['native_frame']
            stream.append(json.dumps({'time_s': camera['time_s'], 'value': value},
                                     sort_keys=True) + '\n')
        path.write_text(''.join(stream), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    for item in description['context_inputs']:
        name = item['name']
        if name == 'reviewed_municipal_red_curb':
            value = {key: scene[key + '_source_sha256'] for key in
                     ('jurisdiction', 'red_curb', 'governed_location', 'sign')}
        elif name == 'reviewed_vehicle_and_activity':
            value = {key: scene[key + '_source_sha256'] for key in
                     ('vehicle_classification', 'vehicle_status', 'activity',
                      'purpose', 'mail_dropbox', 'mail_activity')}
        else:
            raise ValueError('unknown red-curb context input')
        path = root / ('context-' + name + '.json')
        path.write_text(json.dumps({name: value}, sort_keys=True) + '\n')
        evidence.append({'name': name, 'unit': item['unit'], 'reference': path.name})
    from worker_exchange.native_output import write_result
    physical = {part: {'status': 'unverified',
                       'method': 'complete original red-curb halt interval and source-bound camera joins',
                       'sources': source_hashes, 'legal_verdict_claimed': False}
                for part in ('setup', 'target', 'maneuver')}
    result = {'case_id': case_id,
              'measured_values': measured,
              'target_checks': [{'target': 'full original red-curb halt interval',
                                 'requested': case.duration_s,
                                 'measured': measured['original_duration_s'],
                                 'method': 'source-bound original start/end events',
                                 'tolerance': .001, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': source_hashes}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'source-bound interval; independent physical and pixel review pending',
              'physical_failure_flags': ['physical outcome unverified'] if diagnostic else [],
              'physical_checks': physical, 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': diagnostic,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'analysis_complete': True, 'diagnostic_fixture': diagnostic,
            'physical_acceptance_claimed': False,
            'measurements': {'red_curb_conditions': {
                'value': measure_red_curb(measured, scene),
                'method': 'measure_red_curb', 'sources': source_hashes}},
            'limitations': ['Municipal red curb, sign, vehicle status and pixels require independent review.',
                            'Synthetic diagnostic sources cannot establish physical or legal findings.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior red-curb analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n', encoding='utf-8')

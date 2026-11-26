"""Independent original rear-driver, signal, lifecycle and media audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rear_signal import CASES, measure_original
from scene_review import reviewed_scene

AID = 'testing__C150640__NRS-484B-413-3__motor_vehicle_driver'
SOURCES = ('rear-signal-history.jsonl', 'rear-signal-scene.json', 'trace.jsonl',
           'video_frames.jsonl', 'road.xodr')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    root = Path(attempt).resolve()
    processing_path = Path(processing_path)
    decode_receipt = Path(decode_receipt)
    suffix = case_id.removeprefix(AID + '__')
    case = next((item for item in CASES if item.case_id == suffix), None)
    if not case_id.startswith(AID + '__') or case is None:
        raise ValueError('wrong rear-signal case identity')
    seal = read(root / 'capture-seal.json')
    if seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(SOURCES) <= set(seal.get('sources', {})):
        raise ValueError('Native seal omits original rear-signal source')
    for name, digest in seal['sources'].items():
        path = root / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError('sealed original missing or changed: ' + name)
    native_exit = read(root / 'native-exit.json')
    if native_exit.get('event') != 'native_exit' or native_exit.get('capture_seal_sha256') != sha(root / 'capture-seal.json'):
        raise ValueError('Native exit does not bind sealed capture')
    owner = read(root / 'owner-release.json')
    if (owner.get('event') != 'owner_released' or owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(root / 'native-exit.json')):
        raise ValueError('owner release missing or stale')
    provenance = read(root / 'acquisition-provenance.json')
    if not protocol_fixture and (provenance.get('provenance_kind') != 'native' or
                                 provenance.get('diagnostic_fixture') is not False):
        raise ValueError('synthetic diagnostic is not original Native delivery')
    config = read(root / 'config.json')
    if (config.get('selected_case_id') != case_id or config.get('law_id') != 'NRS-484B-413-3' or
            config.get('cell_id') != 'C150640' or config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('original rear-signal config identity differs')
    history = rows(root / 'rear-signal-history.jsonl')
    trace = rows(root / 'trace.jsonl')
    mapping = rows(root / 'video_frames.jsonl')
    if not history or len(history) != len(trace) or len(history) != len(mapping) or len(history) != seal.get('frames'):
        raise ValueError('original rear-signal frame streams incomplete')
    for i, (participant, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get('carla_frame'), video.get('time_s'))
        if (video.get('video_frame') != i or
                (participant.get('original_frame'), participant.get('time_s')) != identity or
                (motion.get('frame'), motion.get('time_s')) != identity):
            raise ValueError('original rear-signal frame/time join changed')
    if not protocol_fixture:
        acquisition = read(root / 'acquisition.json')
        for name in (*SOURCES, 'carla_recorder.log', *[name + '.mkv' for name in CAMERAS]):
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(root / name)):
                raise ValueError('original rear-signal source absent or stale: ' + name)
        scene = reviewed_scene(root / 'reviewed-scene-packet/scene.json', case_id)
        if read(root / 'rear-signal-scene.json') != scene:
            raise ValueError('saved scene differs from reviewed original packet')
        measured = measure_original(history, scene, case)
        if measured.get('frame_count') != 900:
            raise ValueError('original rear-signal 900-frame measurement absent')
    processing = read(processing_path)
    if (processing.get('format') != 'worker-saved-processing' or processing.get('passed') is not True or
            processing.get('recorded_only') is not True or processing.get('case_id') != case_id):
        raise ValueError('saved-only processing receipt absent or failed')
    if not protocol_fixture:
        for name in SOURCES:
            if processing.get('original_source_hashes', {}).get(name) != sha(root / name):
                raise ValueError('saved processing source binding stale: ' + name)
    result_path = Path(processing.get('result', ''))
    if not result_path.is_file() or processing.get('result_sha256') != sha(result_path):
        raise ValueError('saved result missing or stale')
    result = read(result_path)
    if result.get('case_id') != case_id or not result.get('physical_checks'):
        raise ValueError('saved physical checks absent or wrong case')
    if not protocol_fixture and not all(result.get(key) is True for key in
                                    ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')):
        raise ValueError('physical completion not confirmed for original rear-signal event')
    video = Path(processing.get('analysis_directory', '')) / 'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping), mapping_sha256=sha(root / 'video_frames.jsonl'))
    if not protocol_fixture:
        pixel = read(root / 'pixel-review.json')
        required = ('one_way_route_visible', 'ego_motion_visible',
                    'rear_vehicle_visible', 'signal_device_visible',
                    'signal_visible_from_rear')
        if case.rear_driver:
            required += ('rear_driver_visible',)
        else:
            required += ('rear_cabin_empty_confirmed',)
        if (not pixel.get('reviewer') or pixel.get('reviewer') == 'CPU fixture' or
                pixel.get('video_sha256') != sha(video) or
                pixel.get('frame_map_sha256') != sha(root / 'video_frames.jsonl') or
                not all(pixel.get(key) is True for key in required)):
            raise ValueError('independent actual-pixel rear-signal review missing or stale')
    comparison_record = None
    if not protocol_fixture:
        fixed_roles = ('jurisdiction', 'map', 'one_way_route', 'stop_footprint',
                       'ego_vehicle', 'ego_driver_control', 'signal_device',
                       'rear_vehicle', 'rear_position', 'rear_motion',
                       'rear_visibility', 'conflict_context', 'official_direction_context')
        comparison_record = {
            'source_kind': 'original_native_capture',
            'fixed_source_sha256': {name: scene['sources'][name]['sha256'] for name in fixed_roles},
            'rear_driver_source_sha256': scene['sources']['rear_driver']['sha256'],
            'camera_plan': config['cameras'], 'duration_s': config['duration_s'],
            'measurement': measured, 'requested_maneuver': config['case']['maneuver'],
            'requested_signal_policy': config['case']['signal_policy'],
            'requested_rear_driver_present': config['case']['rear_driver_present']}
    return {'format': 'worker-delivery-audit', 'passed': not protocol_fixture,
            'protocol_fixture_checked': protocol_fixture, 'case_id': case_id,
            'assignment_id': AID, 'frame_count': len(mapping),
            'native_result_sha256': sha(result_path),
            'capture_seal_sha256': sha(root / 'capture-seal.json'),
            'frame_map_sha256': sha(root / 'video_frames.jsonl'),
            'video_sha256': sha(video), 'source_decode_receipt_path': str(decode_receipt),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': sha(__file__),
            'physical_acceptance_claimed': not protocol_fixture, 'legal_verdict': None,
            'comparison_record': comparison_record}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'processing', 'decode-receipt', 'case'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--protocol-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt, args.case,
                           protocol_fixture=args.protocol_fixture), indent=2))


if __name__ == '__main__':
    main()

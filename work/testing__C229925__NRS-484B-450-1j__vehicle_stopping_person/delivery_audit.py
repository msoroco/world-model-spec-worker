"""Independent original entrance, lifecycle, physical and pixel audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from fire_entrance_measurements import measure
from fire_station_scene import ASSIGNMENT, case_by_id
from site_review import reviewed_site


SOURCES = ('fire-entrance-context.json', 'fire-entrance-trace.jsonl',
           'fire-source-receipt.json', 'trace.jsonl', 'video_frames.jsonl',
           'road.xodr')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line]


def terminal_halt(history, scene, case):
    """Engineering completion only; no statutory foot or necessity decision."""
    if len(history) != 900:
        raise ValueError('original full-duration entrance halt missing')
    if max(row['speed_mps'] for row in history[:700]) <= .25:
        raise ValueError('original approach motion absent')
    tail = history[-40:]
    target = scene['vehicle_target_xy']
    forward = scene['road_forward_xy']
    origin = scene['road_origin_xy']
    entrance = scene['entrance_start_xy']
    entrance_side = (forward[0]*(entrance[1]-origin[1]) -
                     forward[1]*(entrance[0]-origin[0]))
    for row in tail:
        vertices = row.get('vehicle_vertices')
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError('terminal original body vertices missing')
        center = [sum(vertex[axis] for vertex in vertices)/8 for axis in (0, 1)]
        distance = math.dist(center, target)
        if distance > 1.25 or row.get('speed_mps', 100) > .1:
            raise ValueError('terminal vehicle body did not hold designed halt')
        if row.get('control_state') != case.activity:
            raise ValueError('terminal original halt activity changed')
        if case.activity in ('stand', 'park') and row.get('control_request', {}).get('hand_brake') is not True:
            raise ValueError('terminal stand or park control not held')
        side_values = [forward[0]*(vertex[1]-origin[1]) -
                       forward[1]*(vertex[0]-origin[0])
                       for vertex in vertices]
        if case.side == 'opposite':
            if not all(value*entrance_side < 0 for value in side_values):
                raise ValueError('terminal body not on opposite highway side')
        elif not all(value*entrance_side > 0 for value in side_values):
            raise ValueError('terminal body not on entrance highway side')
    if case.circumstance == 'traffic_conflict':
        if (len({row.get('traffic_vehicle_id') for row in history}) != 1 or
                history[0].get('traffic_vehicle_id') is None or
                max(row.get('traffic_speed_mps') or 0 for row in history) <= .25):
            raise ValueError('original conflicting traffic motion absent')
    return {'tail_frames': 40, 'terminal_body_target_tolerance_m': 1.25,
            'terminal_speed_tolerance_mps': .1,
            'legal_distance_or_exception_decided': False}


def audit(attempt, processing_path, decode_receipt, case_id, *,
          protocol_fixture=False, media_verify=None):
    root = Path(attempt).resolve()
    case = case_by_id(case_id)
    if case is None:
        raise ValueError('wrong fire-station case identity')
    seal = read(root / 'capture-seal.json')
    if seal.get('events') != ['capture_finished', 'encoders_closed',
                              'restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(SOURCES) <= set(seal.get('sources', {})):
        raise ValueError('Native seal omits original entrance source')
    for name, digest in seal['sources'].items():
        path = root / name
        if not path.is_file() or sha(path) != digest:
            raise ValueError('sealed original missing or changed: ' + name)
    native_exit = read(root / 'native-exit.json')
    if (native_exit.get('event') != 'native_exit' or
            native_exit.get('capture_seal_sha256') != sha(root / 'capture-seal.json')):
        raise ValueError('Native exit does not bind sealed capture')
    owner = read(root / 'owner-release.json')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_exit_sha256') != sha(root / 'native-exit.json')):
        raise ValueError('owner release missing or stale')
    provenance = read(root / 'acquisition-provenance.json')
    if not protocol_fixture and (provenance.get('provenance_kind') != 'native' or
                                 provenance.get('diagnostic_fixture') is not False):
        raise ValueError('synthetic diagnostic is not original Native delivery')
    config = read(root / 'config.json')
    if (config.get('selected_case_id') != case_id or
            config.get('law_id') != 'NRS-484B-450-1j' or
            config.get('cell_id') != 'C229925' or
            config.get('actor') != 'vehicle_stopping_person'):
        raise ValueError('original fire-station config identity differs')
    history, trace, mapping = (rows(root / name) for name in
                               ('fire-entrance-trace.jsonl', 'trace.jsonl',
                                'video_frames.jsonl'))
    if (not history or len(history) != len(trace) or
            len(history) != len(mapping) or len(history) != seal.get('frames')):
        raise ValueError('original entrance frame streams incomplete')
    for index, (body, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get('carla_frame'), video.get('time_s'))
        if (video.get('video_frame') != index or
                (body.get('frame'), body.get('time_s')) != identity or
                (motion.get('frame'), motion.get('time_s')) != identity):
            raise ValueError('original entrance frame/time join changed')
    measured = None
    packet = None
    if not protocol_fixture:
        acquisition = read(root / 'acquisition.json')
        for name in (*SOURCES, 'carla_recorder.log',
                     *[camera + '.mkv' for camera in CAMERAS]):
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(root / name)):
                raise ValueError('original entrance source absent or stale: ' + name)
        packet, _ = reviewed_site(root / 'reviewed-fire-station-packet/site.json',
                                  case_id)
        context = read(root / 'fire-entrance-context.json')
        if {key: value for key, value in context.items() if key not in
            ('case_id', 'circumstance', 'activity')} != packet['scene']:
            raise ValueError('saved entrance context differs from reviewed packet')
        measured = measure(case_id, root / 'fire-entrance-context.json',
                           root / 'fire-entrance-trace.jsonl',
                           root / 'fire-source-receipt.json')
        terminal_halt(history, packet['scene'], case)
        if (measured.get('case_id') != case_id or len(history) != 900 or
                read(root / 'fire-entrance-measurement.json') != measured):
            raise ValueError('original 900-frame entrance measurement absent')
    processing = read(processing_path)
    if (processing.get('format') != 'worker-saved-processing' or
            processing.get('passed') is not True or
            processing.get('recorded_only') is not True or
            processing.get('case_id') != case_id):
        raise ValueError('saved-only processing receipt absent or failed')
    if not protocol_fixture:
        for name in SOURCES:
            if processing.get('original_source_hashes', {}).get(name) != sha(root / name):
                raise ValueError('saved processing source binding stale: ' + name)
    result_path = Path(processing.get('result', ''))
    if (not result_path.is_file() or
            processing.get('result_sha256') != sha(result_path)):
        raise ValueError('saved result missing or stale')
    result = read(result_path)
    if result.get('case_id') != case_id or not result.get('physical_checks'):
        raise ValueError('saved physical checks absent or wrong case')
    if not protocol_fixture and not all(result.get(key) is True for key in
                                    ('setup_confirmed', 'behavior_attempted',
                                     'maneuver_completed')):
        raise ValueError('physical entrance halt not confirmed')
    video = Path(processing.get('analysis_directory', '')) / 'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(root / 'video_frames.jsonl'))
    if not protocol_fixture:
        pixel = read(root / 'pixel-review.json')
        if (not pixel.get('reviewer') or pixel['reviewer'] == 'CPU fixture' or
                pixel.get('video_sha256') != sha(video) or
                pixel.get('frame_map_sha256') != sha(root / 'video_frames.jsonl') or
                not all(pixel.get(key) is True for key in
                        ('station_visible', 'entrance_visible',
                         'vehicle_body_visible', 'highway_sides_visible',
                         'halt_activity_visible', 'exception_context_visible'))):
            raise ValueError('independent actual-pixel entrance review missing or stale')
    comparison_record = None
    if not protocol_fixture:
        comparison_record = {
            'source_kind': 'original_native_capture',
            'source_sha256': {name: source['sha256']
                              for name, source in packet['sources'].items()},
            'camera_plan': config['cameras'],
            'duration_s': config['duration_s'],
            'measurement': measured,
            'side_request': case.side,
            'activity_request': case.activity,
            'distance_request_ft': case.distance_ft,
            'circumstance_request': case.circumstance,
            'station_is_fire': packet['scene']['station_is_fire'],
            'highway_public_use': packet['scene']['highway_public_use']}
    return {
        'format': 'worker-delivery-audit',
        'passed': not protocol_fixture,
        'protocol_fixture_checked': protocol_fixture,
        'case_id': case_id, 'assignment_id': ASSIGNMENT,
        'frame_count': len(mapping),
        'native_result_sha256': sha(result_path),
        'capture_seal_sha256': sha(root / 'capture-seal.json'),
        'frame_map_sha256': sha(root / 'video_frames.jsonl'),
        'video_sha256': sha(video),
        'source_decode_receipt_path': str(decode_receipt),
        'source_decode_receipt_sha256': sha(decode_receipt),
        'auditor_path': str(Path(__file__).resolve()),
        'auditor_sha256': sha(__file__),
        'physical_acceptance_claimed': not protocol_fixture,
        'legal_verdict': None,
        'comparison_record': comparison_record}


def main():
    parser = argparse.ArgumentParser()
    for name in ('attempt', 'processing', 'decode-receipt', 'case'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--protocol-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt,
                           args.case, protocol_fixture=args.protocol_fixture),
                     indent=2))


if __name__ == '__main__':
    main()

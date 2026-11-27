"""Independent original roadwork, lifecycle, physical and pixel acceptance audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from excavation_park import CASES, measure_original
from site_review import reviewed_site

AID = 'testing__C229405__NRS-484B-450-1k__motor_vehicle_driver'
SOURCES = ('excavation-history.jsonl', 'excavation-site.json', 'trace.jsonl',
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
    suffix = case_id.removeprefix(AID + '__')
    case = next((item for item in CASES if item.case_id == suffix), None)
    if not case_id.startswith(AID + '__') or case is None:
        raise ValueError('wrong roadwork case identity')
    seal = read(root / 'capture-seal.json')
    if seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified']:
        raise ValueError('Native capture lifecycle incomplete')
    if not set(SOURCES) <= set(seal.get('sources', {})):
        raise ValueError('Native seal omits original excavation source')
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
    if (config.get('selected_case_id') != case_id or config.get('law_id') != 'NRS-484B-450-1k' or
            config.get('cell_id') != 'C229405' or config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('original roadwork config identity differs')
    history, trace, mapping = (rows(root / name) for name in
                               ('excavation-history.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    if not history or len(history) != len(trace) or len(history) != len(mapping) or len(history) != seal.get('frames'):
        raise ValueError('original excavation frame streams incomplete')
    for i, (body, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get('carla_frame'), video.get('time_s'))
        if (video.get('video_frame') != i or
                (body.get('original_frame'), body.get('time_s')) != identity or
                (motion.get('frame'), motion.get('time_s')) != identity):
            raise ValueError('original excavation frame/time join changed')
    measured = None
    packet = None
    if not protocol_fixture:
        acquisition = read(root / 'acquisition.json')
        for name in (*SOURCES, 'carla_recorder.log', *[camera + '.mkv' for camera in CAMERAS]):
            if acquisition.get(name, {}).get('kind') != 'original_native' or acquisition[name].get('sha256') != sha(root / name):
                raise ValueError('original excavation source absent or stale: ' + name)
        packet, _ = reviewed_site(root / 'reviewed-site-packet/site.json', case_id)
        if read(root / 'excavation-site.json') != packet:
            raise ValueError('saved site differs from reviewed original packet')
        measured = measure_original(history, packet['scene'], case)
        if measured.get('frame_count') != 900 or read(root / 'excavation-measurement.json') != measured:
            raise ValueError('original 900-frame roadwork measurement absent')
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
        raise ValueError('physical completion not confirmed for original roadwork')
    video = Path(processing.get('analysis_directory', '')) / 'raw.mkv'
    if not video.is_file():
        raise ValueError('saved primary video missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping), mapping_sha256=sha(root / 'video_frames.jsonl'))
    if not protocol_fixture:
        pixel = read(root / 'pixel-review.json')
        if (not pixel.get('reviewer') or pixel['reviewer'] == 'CPU fixture' or
                pixel.get('video_sha256') != sha(video) or
                pixel.get('frame_map_sha256') != sha(root / 'video_frames.jsonl') or
                not all(pixel.get(key) is True for key in
                        ('excavation_visible', 'vehicle_body_visible', 'passing_traffic_visible',
                         'halt_activity_visible', 'exception_context_visible'))):
            raise ValueError('independent actual-pixel roadwork review missing or stale')
    comparison_record = None
    if not protocol_fixture:
        fixed = ('map', 'highway', 'excavation', 'traffic')
        comparison_record = {
            'source_kind': 'original_native_capture',
            'fixed_source_sha256': {name: packet['sources'][name]['sha256'] for name in fixed},
            'camera_plan': config['cameras'], 'duration_s': config['duration_s'],
            'measurement': measured, 'requested_relation': config['case']['relation'],
            'activity': config['case']['halt_activity'],
            'passage_probe': config['case']['passage_probe'],
            'exception': config['case']['exception_context']}
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
    print(json.dumps(audit(args.attempt, args.processing, args.decode_receipt,
                           args.case, protocol_fixture=args.protocol_fixture), indent=2))


if __name__ == '__main__':
    main()

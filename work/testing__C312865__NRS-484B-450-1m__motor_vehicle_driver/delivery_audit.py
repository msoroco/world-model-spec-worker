"""Independent source, lifecycle, frame, physical and pixel audit for a tunnel halt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from site_review import reviewed_site
from tunnel import CASES, measure_original

AID = 'testing__C312865__NRS-484B-450-1m__motor_vehicle_driver'
SOURCES = ('tunnel-history.jsonl', 'tunnel-site.json', 'trace.jsonl',
           'video_frames.jsonl', 'road.xodr')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    root = Path(attempt).resolve()
    suffix = case_id.removeprefix(AID + '__')
    case = next((item for item in CASES if item.case_id == suffix), None)
    require(case_id.startswith(AID + '__') and case is not None, 'wrong tunnel case identity')
    seal = read(root / 'capture-seal.json')
    require(seal.get('events') == ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'Native capture lifecycle incomplete')
    require(set(SOURCES) <= set(seal.get('sources', {})), 'Native seal omits original tunnel source')
    for name, digest in seal['sources'].items():
        path = root / name
        require(path.is_file() and sha(path) == digest,
                'sealed original missing or changed: ' + name)
    native_exit = read(root / 'native-exit.json')
    require(native_exit.get('event') == 'native_exit' and
            native_exit.get('capture_seal_sha256') == sha(root / 'capture-seal.json'),
            'Native exit does not bind sealed capture')
    owner = read(root / 'owner-release.json')
    require(owner.get('event') == 'owner_released' and owner.get('operator_attested') is True and
            owner.get('native_exit_sha256') == sha(root / 'native-exit.json'),
            'owner release missing or stale')
    provenance = read(root / 'acquisition-provenance.json')
    if not protocol_fixture:
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'synthetic diagnostic is not original Native delivery')
    config = read(root / 'config.json')
    require(config.get('selected_case_id') == case_id and
            config.get('law_id') == 'NRS-484B-450-1m' and
            config.get('cell_id') == 'C312865' and
            config.get('actor') == 'motor_vehicle_driver',
            'original tunnel config identity differs')
    history, trace, mapping = (rows(root / name) for name in
                               ('tunnel-history.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    require(history and len(history) == len(trace) == len(mapping) == seal.get('frames'),
            'original tunnel frame streams incomplete')
    for i, (body, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get('carla_frame'), video.get('time_s'))
        require(video.get('video_frame') == i and
                (body.get('original_frame'), body.get('time_s')) == identity and
                (motion.get('frame'), motion.get('time_s')) == identity,
                'original tunnel frame/time join changed')
    measured = None
    packet = None
    if not protocol_fixture:
        acquisition = read(root / 'acquisition.json')
        for name in (*SOURCES, 'carla_recorder.log', *[camera + '.mkv' for camera in CAMERAS]):
            require(acquisition.get(name, {}).get('kind') == 'original_native' and
                    acquisition[name].get('sha256') == sha(root / name),
                    'original tunnel source absent or stale: ' + name)
        packet, _ = reviewed_site(root / 'reviewed-site-packet/site.json', case_id)
        require(read(root / 'tunnel-site.json') == packet,
                'saved site differs from reviewed original packet')
        measured = measure_original(history, packet['site'], case)
        require(measured.get('original_frames') == 900 and
                read(root / 'tunnel-measurement.json') == measured,
                'original 900-frame tunnel measurement absent')
        require((measured['terminal_body_inside_tunnel'] if case.endpoint == 'inside_tunnel'
                 else measured['terminal_body_outside_tunnel']) is True,
                'original terminal tunnel body relation wrong')
    processing = read(processing_path)
    require(processing.get('format') == 'worker-saved-processing' and
            processing.get('passed') is True and processing.get('recorded_only') is True and
            processing.get('case_id') == case_id,
            'saved-only processing receipt absent or failed')
    if not protocol_fixture:
        for name in SOURCES:
            require(processing.get('original_source_hashes', {}).get(name) == sha(root / name),
                    'saved processing source binding stale: ' + name)
    result_path = Path(processing.get('result', ''))
    require(result_path.is_file() and processing.get('result_sha256') == sha(result_path),
            'saved result missing or stale')
    result = read(result_path)
    require(result.get('case_id') == case_id and result.get('physical_checks'),
            'saved physical checks absent or wrong case')
    if not protocol_fixture:
        require(all(result.get(key) is True for key in
                    ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')),
                'physical completion not confirmed for original tunnel')
    video = Path(processing.get('analysis_directory', '')) / 'raw.mkv'
    require(video.is_file(), 'saved primary video missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(root / 'video_frames.jsonl'))
    if not protocol_fixture:
        pixel = read(root / 'pixel-review.json')
        require(bool(pixel.get('reviewer')) and pixel['reviewer'] != 'CPU fixture' and
                pixel.get('video_sha256') == sha(video) and
                pixel.get('frame_map_sha256') == sha(root / 'video_frames.jsonl') and
                all(pixel.get(key) is True for key in
                    ('portal_visible', 'ego_visible', 'tunnel_boundary_visible',
                     'halt_activity_visible', 'other_traffic_visible',
                     'exception_context_visible')),
                'independent actual-pixel tunnel review missing or stale')
    comparison_record = None
    if not protocol_fixture:
        fixed = ('map', 'highway', 'tunnel', 'portal', 'route',
                 'ego_blueprint', 'other_blueprint')
        comparison_record = {
            'source_kind': 'original_native_capture',
            'fixed_source_sha256': {name: packet['sources'][name]['sha256'] for name in fixed},
            'camera_plan': config['cameras'], 'duration_s': config['duration_s'],
            'measurement': measured, 'requested_endpoint': config['case']['endpoint'],
            'activity': config['case']['halt_activity'],
            'exception': config['case']['exception_probe']}
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

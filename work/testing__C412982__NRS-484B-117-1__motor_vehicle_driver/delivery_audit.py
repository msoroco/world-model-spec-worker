"""Independent original sidewalk capture and saved-result acceptance audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sidewalk_case import BY_SUFFIX, validate_case_site
from sidewalk_measure import measure_frame
from site_review import reviewed_site

AID = 'testing__C412982__NRS-484B-117-1__motor_vehicle_driver'
SOURCES = ('sidewalk-history.jsonl', 'sidewalk-site.json', 'trace.jsonl',
           'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip()]


def require(ok, message):
    if not ok:
        raise ValueError(message)


def audit(attempt, processing_path, decode_receipt, case_id, *, protocol_fixture=False,
          media_verify=None):
    root = Path(attempt).resolve()
    suffix = case_id.removeprefix(AID + '__')
    case = BY_SUFFIX.get(suffix)
    require(case_id.startswith(AID + '__') and case is not None,
            'wrong sidewalk case identity')
    seal = read(root / 'capture-seal.json')
    require(seal.get('events') == ['capture_finished', 'encoders_closed',
                                  'restoration_verified'], 'Native capture lifecycle incomplete')
    required_sources = SOURCES if not protocol_fixture else SOURCES[:5] + SOURCES[6:]
    require(set(required_sources) <= set(seal.get('sources', {})),
            'Native seal omits original sidewalk source')
    for name, digest in seal['sources'].items():
        path = root / name
        require(path.is_file() and sha(path) == digest,
                'sealed original missing or changed: ' + name)
    native_exit = read(root / 'native-exit.json')
    require(native_exit.get('event') == 'native_exit' and
            native_exit.get('capture_seal_sha256') == sha(root / 'capture-seal.json'),
            'Native exit does not bind sealed capture')
    owner = read(root / 'owner-release.json')
    require(owner.get('event') == 'owner_released' and
            owner.get('operator_attested') is True and
            owner.get('native_exit_sha256') == sha(root / 'native-exit.json'),
            'owner release missing or stale')
    provenance = read(root / 'acquisition-provenance.json')
    if not protocol_fixture:
        require(provenance.get('provenance_kind') == 'native' and
                provenance.get('diagnostic_fixture') is False,
                'synthetic diagnostic is not original Native delivery')
    config = read(root / 'config.json')
    require(config.get('selected_case_id') == case_id and
            config.get('law_id') == 'NRS-484B-117-1' and
            config.get('cell_id') == 'C412982' and
            config.get('actor') == 'motor_vehicle_driver',
            'original sidewalk config identity differs')
    history = rows(root / 'sidewalk-history.jsonl')
    trace = rows(root / 'trace.jsonl')
    mapping = rows(root / 'video_frames.jsonl')
    require(history and len(history) == len(trace) == len(mapping) == seal.get('frames'),
            'original sidewalk frame streams incomplete')
    for index, (body, motion, video) in enumerate(zip(history, trace, mapping)):
        identity = (video.get('carla_frame'), video.get('time_s'))
        require(video.get('video_frame') == index and
                (body.get('original_frame'), body.get('time_s')) == identity and
                (motion.get('frame'), motion.get('time_s')) == identity,
                'original sidewalk frame/time join changed')
    site = read(root / 'sidewalk-site.json')
    if not protocol_fixture:
        acquisition = read(root / 'acquisition.json')
        for name in SOURCES:
            require(acquisition.get(name, {}).get('kind') == 'original_native' and
                    acquisition[name].get('sha256') == sha(root / name),
                    'original sidewalk source absent or stale: ' + name)
        packet = root / 'reviewed-site-packet/site.json'
        require(read(packet) == site and reviewed_site(packet, case_id) == site,
                'saved site differs from reviewed original packet')
        require(len(history) == 900, 'original sidewalk 900-frame measurement absent')
        validate_case_site(case, site)
    measured = [measure_frame(row, site) for row in history]
    peak = max(row['sidewalk_overlap_area_m2'] for row in measured)
    entrances = {name: max(row['entrance_overlap_area_m2'][name] for row in measured)
                 for name in site['entrance_polygons_xy']}
    processing = read(processing_path)
    require(processing.get('format') == 'worker-saved-processing' and
            processing.get('passed') is True and processing.get('recorded_only') is True and
            processing.get('case_id') == case_id and
            processing.get('originals_preserved') is True,
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
        require(result.get('diagnostic_fixture') is False and
                all(result.get(key) is True for key in
                    ('setup_confirmed', 'behavior_attempted', 'maneuver_completed')),
                'physical completion not confirmed for original sidewalk')
    video = Path(processing.get('analysis_directory', '')) / 'raw.mkv'
    require(video.is_file(), 'saved primary video missing')
    if media_verify is None:
        from worker_exchange.media import verify_receipt
        media_verify = verify_receipt
    media_verify(video, decode_receipt, len(mapping),
                 mapping_sha256=sha(root / 'video_frames.jsonl'))
    if not protocol_fixture:
        pixel = read(root / 'pixel-review.json')
        require(pixel.get('reviewer') and pixel.get('reviewer') != 'CPU fixture' and
                pixel.get('video_sha256') == sha(video) and
                pixel.get('frame_map_sha256') == sha(root / 'video_frames.jsonl') and
                all(pixel.get(key) is True for key in
                    ('sidewalk_boundary_visible', 'vehicle_body_visible',
                     'entrance_context_visible', 'operator_context_visible')),
                'independent actual-pixel sidewalk review missing or stale')
    fixed_roles = ('jurisdiction', 'map', 'curb_or_highway_lateral_line',
                   'property_line', 'pedestrian_purpose', 'sidewalk_polygon')
    comparison = None if protocol_fixture else {
        'source_kind': 'original_native_capture',
        'fixed_source_sha256': {name: site['sources'][name]['sha256']
                                for name in fixed_roles},
        'camera_plan': config['cameras'], 'duration_s': config['duration_s'],
        'requested_relation': suffix,
        'maximum_sidewalk_body_overlap_m2': peak,
        'maximum_entrance_body_overlap_m2': entrances,
        'vehicle_design': site['vehicle_design'],
        'operator_context': site['operator_context'],
        'body_geometry_source_sha256': site['body_geometry_source_sha256'],
        'frame_count': len(history)}
    return {'format': 'worker-delivery-audit', 'passed': not protocol_fixture,
            'protocol_fixture_checked': protocol_fixture,
            'case_id': case_id, 'assignment_id': AID,
            'frame_count': len(mapping), 'capture_seal_sha256': sha(root / 'capture-seal.json'),
            'native_result_sha256': sha(result_path),
            'frame_map_sha256': sha(root / 'video_frames.jsonl'),
            'video_sha256': sha(video), 'source_decode_receipt_path': str(decode_receipt),
            'source_decode_receipt_sha256': sha(decode_receipt),
            'auditor_path': str(Path(__file__).resolve()), 'auditor_sha256': sha(__file__),
            'physical_acceptance_claimed': not protocol_fixture,
            'legal_verdict': None, 'comparison_record': comparison}


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

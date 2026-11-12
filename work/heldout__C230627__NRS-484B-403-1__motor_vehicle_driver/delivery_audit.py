"""Independent C230627 original-source and four-camera delivery audit."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from u_turn_measurement import measure
from u_turn_finalizer import (measure_built_frontage, measure_mapped_device,
                              measure_mapped_divider, measure_school_zone_candidate)


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('u_turn_motion.jsonl', 'u_turn_context.json',
           'video_frames.jsonl', 'trace.jsonl')
PREFIX = 'heldout__C230627__NRS-484B-403-1__motor_vehicle_driver__'


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def audit_attempt(attempt, report, *, decoder=None):
    root = Path(attempt)
    report = json.loads(Path(report).read_text()) if not isinstance(report, dict) else report
    case_id = report.get('case_id', '')
    if not case_id.startswith(PREFIX):
        raise ValueError('Wrong C230627 exact delivery case')
    observation = report['measurements']['u_turn_observation']
    hashes = observation['sources']
    if set(hashes) != set(SOURCES):
        raise ValueError('Original U-turn source inventory differs')
    for name, expected in hashes.items():
        path = root/name
        if not path.is_file() or _digest(path) != expected:
            raise ValueError('Original U-turn source hash differs: ' + name)
    measured = measure(root/'u_turn_motion.jsonl', root/'u_turn_context.json')
    if measured != observation['value']:
        raise ValueError('Independent U-turn measurement differs')
    if case_id.endswith('__prohibition_403_2'):
        device = report['measurements'].get('mapped_no_u_turn_device')
        if not isinstance(device, dict) or set(device.get('sources', {})) != {
                'u_turn_device.json', 'u_turn_context.json'}:
            raise ValueError('Mapped device original source inventory differs')
        for name, expected in device['sources'].items():
            path = root/name
            if not path.is_file() or _digest(path) != expected:
                raise ValueError('Mapped device original source hash differs: ' + name)
        if measure_mapped_device(root/'u_turn_device.json',
                                 root/'u_turn_context.json') != device['value']:
            raise ValueError('Independent mapped device measurement differs')
    if case_id.endswith('__prohibition_403_3'):
        frontage = report['measurements'].get('built_frontage_candidate')
        if not isinstance(frontage, dict) or set(frontage.get('sources', {})) != {
                'u_turn_403_3_frontage.json', 'u_turn_context.json'}:
            raise ValueError('Built frontage original source inventory differs')
        for name, expected in frontage['sources'].items():
            path = root/name
            if not path.is_file() or _digest(path) != expected:
                raise ValueError('Built frontage original source hash differs: ' + name)
        if measure_built_frontage(root/'u_turn_403_3_frontage.json',
                                  root/'u_turn_context.json') != frontage['value']:
            raise ValueError('Independent built frontage measurement differs')
    if case_id.endswith('__prohibition_227'):
        divider = report['measurements'].get('divider_candidate')
        if not isinstance(divider,dict) or set(divider.get('sources',{})) != {
                'u_turn_227_divider.json','u_turn_context.json'}:
            raise ValueError('Mapped divider original source inventory differs')
        for name,expected in divider['sources'].items():
            path=root/name
            if not path.is_file() or _digest(path) != expected:
                raise ValueError('Mapped divider original source hash differs: '+name)
        if measure_mapped_divider(root/'u_turn_227_divider.json',
                                  root/'u_turn_context.json') != divider['value']:
            raise ValueError('Independent mapped divider measurement differs')
    if case_id.endswith('__prohibition_363'):
        school = report['measurements'].get('school_zone_candidate')
        if not isinstance(school, dict) or set(school.get('sources', {})) != {
                'u_turn_363_school.json', 'u_turn_context.json'}:
            raise ValueError('School-zone original source inventory differs')
        for name, expected in school['sources'].items():
            path = root/name
            if not path.is_file() or _digest(path) != expected:
                raise ValueError('School-zone original source hash differs: ' + name)
        if measure_school_zone_candidate(root/'u_turn_363_school.json',
                                         root/'u_turn_context.json') != school['value']:
            raise ValueError('Independent school-zone measurement differs')
    mapping, trace, motion = (_rows(root/name) for name in
                              ('video_frames.jsonl', 'trace.jsonl',
                               'u_turn_motion.jsonl'))
    if not mapping or len(mapping) != len(trace) or len(mapping) != len(motion):
        raise ValueError('Original U-turn frames incomplete')
    for index, (frame, capture, row) in enumerate(zip(mapping, trace, motion)):
        if (frame.get('video_frame') != index or
                (capture.get('frame'), capture.get('time_s')) !=
                (frame.get('carla_frame'), frame.get('time_s')) or
                (row.get('frame'), row.get('time_s')) !=
                (frame.get('carla_frame'), frame.get('time_s'))):
            raise ValueError('Original U-turn frame join differs')
    if decoder is None:
        from worker_exchange.media import audit as decoder
    cameras = {}
    for name in CAMERAS:
        path = root/(name+'.mkv')
        if not path.is_file():
            raise ValueError('Missing original U-turn camera: ' + name)
        decoded = decoder(path, len(mapping),
                          mapping_sha256=_digest(root/'video_frames.jsonl'))
        if decoded.get('frames') != len(mapping):
            raise ValueError('Original U-turn camera frame count differs: ' + name)
        cameras[name] = {'source_sha256': _digest(path), 'decode': decoded}
    return {'format': 'worker-C230627-source-audit', 'case_id': case_id,
            'source_hashes': hashes, 'frame_count': len(mapping),
            'camera_decodes': cameras, 'measurement_recomputed': True,
            'physical_visibility_claimed': False, 'legal_safety_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--tamper-motion-hash', action='store_true')
    parser.add_argument('--tamper-frontage-hash', action='store_true')
    parser.add_argument('--tamper-divider-hash', action='store_true')
    parser.add_argument('--tamper-school-hash', action='store_true')
    args = parser.parse_args()
    report = json.loads(Path(args.report).read_text())
    if args.tamper_motion_hash:
        report['measurements']['u_turn_observation']['sources']['u_turn_motion.jsonl'] = '0'*64
    if args.tamper_frontage_hash:
        report['measurements']['built_frontage_candidate']['sources']['u_turn_403_3_frontage.json'] = '0'*64
    if args.tamper_divider_hash:
        report['measurements']['divider_candidate']['sources']['u_turn_227_divider.json'] = '0'*64
    if args.tamper_school_hash:
        report['measurements']['school_zone_candidate']['sources']['u_turn_363_school.json'] = '0'*64
    result = audit_attempt(args.attempt, report)
    if result['case_id'] != args.case:
        raise ValueError('C230627 delivery audit case argument differs')
    print(json.dumps({'case_id': args.case, 'frame_count': result['frame_count'],
                      'measurement_recomputed': True,
                      'camera_sources': list(result['camera_decodes']),
                      'physical_visibility_claimed': False}))


if __name__ == '__main__':
    main()

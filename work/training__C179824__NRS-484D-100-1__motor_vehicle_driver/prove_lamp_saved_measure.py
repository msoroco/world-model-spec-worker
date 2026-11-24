"""Synthetic source-shape diagnostics; no original photons or legal verdict."""
import copy
import hashlib
import json
from pathlib import Path

from lamp_saved_measure import ASSIGNMENT, CAMERAS, measure, measure_original


def enc(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()


def lines(rows):
    return ('\n'.join(json.dumps(row, sort_keys=True) for row in rows) + '\n').encode()


def sample(lamps_on=True, active=True):
    h = hashlib.sha256(b'synthetic lamp diagnostic source only').hexdigest()
    context = {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
               'highway_source_sha256': h, 'vehicle_class_source_sha256': h,
               'device_content_source_sha256': h, 'device_authority_source_sha256': h,
               'device_placement_source_sha256': h, 'device_timing_source_sha256': h,
               'state': 'Nevada', 'public_highway': True,
               'vehicle_class': 'ordinary_motor_vehicle', 'directive': 'use_lamps',
               'device_official': True, 'road_id': '1', 'device_governs_road_id': '1'}
    frames = [{'video_frame': i, 'native_frame': 200+i, 'time_s': i/20,
               'vehicle_id': 'ego', 'road_id': '1', 'speed_mps': 4,
               'camera_native_frames': {name: 200+i for name in CAMERAS},
               'device_active': active and i >= 100,
               'headlamp_setting_on': lamps_on, 'position_lamp_setting_on': lamps_on}
              for i in range(600)]
    return {'assignment_id': ASSIGNMENT, 'source_kind': 'synthetic_native_sample',
            'vehicle_id': 'ego', 'frames': frames}, context


def reject(packet, context, message):
    try:
        measure(enc(packet), enc(context))
    except ValueError as exc:
        if str(exc) != message:
            raise
        return
    raise RuntimeError('bad source accepted: ' + message)


def main():
    root = Path(__file__).resolve().parents[2]
    source = root / 'inputs' / ASSIGNMENT
    hashes = {n: hashlib.sha256((source/n).read_bytes()).hexdigest()
              for n in ('assignment.json', 'witnesses.json')}
    law = json.loads((source/'assignment.json').read_text())['law']['text']
    if ('(c) When directed by an official traffic control device' not in law or
            'one-half hour after sunset' not in law or '1,000 feet ahead' not in law):
        raise ValueError('frozen law text changed')
    positives = {}
    for name, on, active in (('lamps_on', True, True), ('lamps_off', False, True),
                             ('inactive_device', True, False)):
        packet, context = sample(on, active)
        result = measure(enc(packet), enc(context))
        if (result['governed_frames'] != (list(range(100, 600)) if active else []) or
                result['both_settings_on_frames'] != (list(range(100, 600)) if active and on else []) or
                result['legal_result'] is not None):
            raise RuntimeError('lamp/device diagnostic mismatch: ' + name)
        positives[name] = result['frames_sha256']
    packet, context = sample()
    failures = [
        ('missing_authority', lambda p,c: c.__setitem__('device_authority_source_sha256',''),
         'device_authority_source_sha256 missing'),
        ('not_highway', lambda p,c: c.__setitem__('public_highway',False),
         'Nevada highway source missing'),
        ('wrong_road', lambda p,c: c.__setitem__('device_governs_road_id','2'),
         'device does not govern roadway'),
        ('missing_lamp_readback', lambda p,c: p['frames'][200].pop('headlamp_setting_on'),
         'lamp readback missing'),
        ('missing_device_timing', lambda p,c: p['frames'][200].pop('device_active'),
         'device timing source missing'),
        ('changed_vehicle', lambda p,c: p['frames'][200].__setitem__('vehicle_id','other'),
         'vehicle identity changed'),
        ('missing_camera', lambda p,c: p['frames'][200]['camera_native_frames'].pop('device_face'),
         'four-camera frame join missing'),
        ('missing_frame', lambda p,c: p['frames'].pop(200),
         'recording shorter than 30 seconds'),
    ]
    for _, change, message in failures:
        p, c = copy.deepcopy(packet), copy.deepcopy(context)
        change(p,c)
        reject(p,c,message)
    road = b'<OpenDRIVE diagnostic="synthetic-shape-only" />'
    context['source_kind'] = 'native_saved_sample'
    context['map_source_sha256'] = hashlib.sha256(road).hexdigest()
    poses = lines(packet['frames'])
    mapping = lines([{'video_frame': f['video_frame'], 'native_frame': f['native_frame'],
                      'time_s': f['time_s'], 'camera_native_frames': f['camera_native_frames']}
                     for f in packet['frames']])
    joined = measure_original(poses, mapping, enc(context), road)
    if joined['both_settings_on_frames'] != list(range(100,600)):
        raise RuntimeError('original lamp join mismatch')
    try:
        measure_original(poses,mapping,enc(context),b'changed map')
    except ValueError as exc:
        if str(exc) != 'OpenDRIVE source hash mismatch':
            raise
    else:
        raise RuntimeError('changed OpenDRIVE accepted')
    print(json.dumps({'passed': True, 'frozen_source_hashes': hashes,
                      'positive_packet_hashes': positives,
                      'negative_checks': [n for n,_,_ in failures] + ['changed_opendrive'],
                      'original_pose_sha256': joined['original_pose_sha256'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()

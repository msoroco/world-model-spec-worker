"""Independent source, participant, frame, pixel and physical diagnostic audit."""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from test_saved_attempt import packet
from delivery_audit import VIEWS, audit_saved_delivery


def ref(path):
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')
    return ref(path)


def run(case, base, output, negative):
    suffix = case.rsplit('__', 1)[1]
    if suffix not in ('green_clear', 'green_vehicle_present', 'green_pedestrian_present', 'green_pedestrian_late'):
        raise ValueError('unknown exact case')
    base.mkdir(parents=True, exist_ok=False)
    p = packet(base, suffix)
    if p['case_id'] != case:
        raise ValueError('wrong exact case')
    other = json.loads((base / p['event_ref']['path']).read_text())[0]['other_users']
    device = write(base / 'other-devices.json', {'survey_status': 'diagnostic_fixture', 'devices': []})
    contexts = {}
    for user in other:
        name = user['lawful_presence_source']
        contexts[user['id']] = write(base / name, {'participant_id': user['id'],
             'lawful_presence': None, 'provenance_kind': 'synthetic_fixture'})
    context = {'official_head_id': 'head-7', 'ego_approach_id': 'north',
               'other_devices_ref': device, 'participant_context_refs': contexts}
    p['context_ref'] = write(base / 'reviewed-context.json', context)
    p['camera_profile_ref'] = write(base / 'camera-profile.json',
             {'fps': 20, 'views': {name: [16, 16] for name in VIEWS}})
    p['camera_profile_sha256'] = p['camera_profile_ref']['sha256']
    p['frame_map_ref'] = write(base / 'frame-map.json',
             [{'index': i, 'frame': i + 1, 'camera_frame_ids': {v: i + 1 for v in VIEWS}}
              for i in range(3)])
    p['camera_media_refs'] = {}
    for view in VIEWS:
        media = base / (view + '.mkv')
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            f'color=c=blue:s=16x16:r=20', '-frames:v', '3', '-c:v', 'ffv1', str(media)],
            check=True, capture_output=True)
        p['camera_media_refs'][view] = ref(media)
    if negative:
        (base / 'approach.mkv').unlink()
    receipt = audit_saved_delivery(p, base, profile={v: (16, 16) for v in VIEWS},
                                   diagnostic_fixture=True)
    physical = json.loads((ROOT / f'physical-{suffix}-complete_motion-result.json').read_text())
    if physical['physical_checks']['maneuver']['status'] != 'met' or not physical['realized_observables']:
        raise ValueError('independent physical diagnostic evidence missing')
    value = {'case_id': case, 'software_audit': receipt, 'physical_fixture_sha256':
             hashlib.sha256((ROOT / f'physical-{suffix}-complete_motion-result.json').read_bytes()).hexdigest(),
             'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                        'actual_pixels', 'physical_completion'],
             'provenance_kind': 'synthetic_fixture', 'native_physical_acceptance_claimed': False}
    write(output, value)
    print(json.dumps({'case_id': case, 'checks': value['checks'],
                      'source_views': sorted(receipt['camera_media']),
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    run(args.case, args.scratch, args.output, args.negative)

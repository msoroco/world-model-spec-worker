"""Synthetic school-zone activation/speed branches and negative source checks."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_school_zone import AID, CAMERAS, COUNT, MPS_PER_MPH, measure


def save(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def reject(root, changed, mutation):
    path = root/changed
    original = path.read_bytes()
    try:
        if changed.endswith('.jsonl'):
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            if mutation == 'frame':
                rows[200]['native_frame'] = rows[199]['native_frame']
            elif mutation == 'provenance':
                rows[200]['source_kind'] = 'original_native_velocity'
            elif mutation == 'road':
                rows[200]['road_id'] = 999
            elif mutation == 'velocity':
                rows[200]['velocity_x_mps'] = float('nan')
            save(path, rows)
        else:
            data = json.loads(path.read_text())
            if mutation == 'camera_hash':
                data['camera_sha256'] = {}
            elif mutation == 'calendar_source':
                del data['calendar_source']
            elif mutation == 'civil_time':
                data['civil_start_iso'] = '2026-11-23T08:00:00'
            elif mutation == 'beacon_fact':
                del data['beacon_flashing']
            path.write_text(json.dumps(data)+'\n')
        try:
            measure(root)
        except ValueError as exc:
            return {'mutation': mutation, 'rejected': str(exc)}
        raise AssertionError('Mutation accepted: '+mutation)
    finally:
        path.write_bytes(original)


def main():
    with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as tmp:
        root = Path(tmp)
        for name in CAMERAS:
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=64x48:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', str(root/('camera_'+name+'.mkv'))], check=True)
        hashes = {('camera_'+name+'.mkv'): hashlib.sha256((root/('camera_'+name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(COUNT)]
        save(root/'video_frames.jsonl', frames)
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic-software-test',
                   'camera_sha256': hashes, 'zone_designation_source': 'synthetic fixture',
                   'zone_sign_source': 'synthetic fixture', 'calendar_source': 'synthetic fixture',
                   'school_hours_source': 'synthetic fixture', 'half_hour_window_source': 'synthetic fixture',
                   'beacon_source': 'synthetic fixture', 'beacon_phase_source': 'synthetic fixture',
                   'nonbeacon_sign_schedule_source': 'synthetic fixture',
                   'vehicle_class_source': 'synthetic fixture', 'civil_time_source': 'synthetic fixture',
                   'road_axis_source': 'synthetic fixture', 'condition_stability_source': 'synthetic fixture',
                   'condition_stable_30s': True, 'civil_start_iso': '2026-11-23T08:00:00-08:00',
                   'zone_designated': True, 'school_session_day': True,
                   'half_hour_window_exception': False, 'beacon_operational': True,
                   'pupils_in_class': True, 'beacon_flashing': True,
                   'nonbeacon_sign_in_effect': True, 'ego_is_motor_vehicle': True,
                   'road_id': 42, 'ego_actor_id': 7,
                   'zone_station_bounds_m': [50.0, 200.0], 'road_axis_xy': [1.0, 0.0]}
        variants = []
        for label, mph, updates in (
                ('active_below', 14.5, {}), ('active_above', 17.0, {}),
                ('no_school_day', 17.0, {'school_session_day': False}),
                ('half_hour_exception', 17.0, {'half_hour_window_exception': True}),
                ('beacon_nonflashing_class', 17.0, {'beacon_flashing': False}),
                ('nonbeacon_sign_off', 17.0, {'beacon_operational': False, 'nonbeacon_sign_in_effect': False}),
                ('nonbeacon_sign_on', 17.0, {'beacon_operational': False, 'nonbeacon_sign_in_effect': True})):
            state = copy.deepcopy(context)
            state.update(updates)
            (root/'school_zone_context.json').write_text(json.dumps(state))
            motion = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                       'ego_actor_id': 7, 'road_id': 42, 'ego_x_m': i*.5, 'ego_y_m': 0.0,
                       'velocity_x_mps': mph*MPS_PER_MPH, 'velocity_y_mps': 0.0,
                       'velocity_z_mps': 0.0} for i in range(COUNT)]
            save(root/'native_motion.jsonl', motion)
            observed = measure(root)
            expected_active = label in ('active_below', 'active_above', 'nonbeacon_sign_on')
            assert observed['reviewed_activation_complete'] == expected_active
            assert len(observed['frames_above_15_mph_in_zone']) == (301 if mph > 15 else 0)
            variants.append({'name': label, 'active': observed['reviewed_activation_complete'],
                             'above_15_zone_frames': len(observed['frames_above_15_mph_in_zone'])})
        negatives = [reject(root, 'native_motion.jsonl', 'frame'),
                     reject(root, 'native_motion.jsonl', 'provenance'),
                     reject(root, 'native_motion.jsonl', 'road'),
                     reject(root, 'native_motion.jsonl', 'velocity'),
                     reject(root, 'school_zone_context.json', 'camera_hash'),
                     reject(root, 'school_zone_context.json', 'calendar_source'),
                     reject(root, 'school_zone_context.json', 'civil_time'),
                     reject(root, 'school_zone_context.json', 'beacon_fact')]
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()

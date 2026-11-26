"""Synthetic school-zone activation/speed branches and negative source checks."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from measure_school_zone import AID, CASE, CAMERAS, COUNT, MPS_PER_MPH, measure
from compare_school_zone import SPECS, case_id, compare


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
            elif mutation == 'direction':
                rows[200]['travel_direction_id'] = 'opposing'
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
            elif mutation == 'speed_limit':
                data['authorized_mph'] = 25
            elif mutation == 'case':
                data['case_id'] = AID+'__probe_01'
            elif mutation == 'original_without_survey':
                data['review_kind'] = 'original_source_review'
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
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', str(root/(name+'.mkv'))], check=True)
        hashes = {(name+'.mkv'): hashlib.sha256((root/(name+'.mkv')).read_bytes()).hexdigest()
                  for name in CAMERAS}
        frames = [{'video_frame': i, 'native_frame': 1000+i, 'time_s': round(i*.05, 4)} for i in range(COUNT)]
        save(root/'video_frames.jsonl', frames)
        context = {'assignment_id': AID, 'case_id': CASE,
                   'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic-software-test',
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
                   'road_id': 42, 'ego_actor_id': 7, 'travel_direction_id': 'surveyed_lane',
                   'authorized_mph': 15,
                   'zone_station_bounds_m': [50.0, 200.0], 'road_axis_xy': [1.0, 0.0]}
        variants = []
        variant_roots = {}
        for suffix, label, mph, updates in (
                ('probe_01', 'active_below', 14.0, {}),
                ('probe_02', 'active_at', 15.0, {}),
                ('probe_03', 'active_above', 17.0, {}),
                ('probe_04', 'no_school_day', 17.0, {'school_session_day': False}),
                ('probe_05', 'half_hour_exception', 17.0, {'half_hour_window_exception': True}),
                ('probe_06', 'beacon_nonflashing_class', 17.0, {'beacon_flashing': False}),
                ('probe_07', 'nonbeacon_sign_on', 17.0, {'beacon_operational': False, 'nonbeacon_sign_in_effect': True}),
                ('probe_08', 'nonbeacon_sign_off', 17.0, {'beacon_operational': False, 'nonbeacon_sign_in_effect': False})):
            state = copy.deepcopy(context)
            state['case_id'] = AID+'__'+suffix
            state.update(updates)
            (root/'school_zone_context.json').write_text(json.dumps(state))
            motion = [{'video_frame': i, 'native_frame': 1000+i, 'source_kind': 'synthetic_native_sample',
                       'ego_actor_id': 7, 'road_id': 42, 'travel_direction_id': 'surveyed_lane',
                       'ego_x_m': i*.5, 'ego_y_m': 0.0,
                       'velocity_x_mps': mph*MPS_PER_MPH, 'velocity_y_mps': 0.0,
                       'velocity_z_mps': 0.0} for i in range(COUNT)]
            save(root/'native_motion.jsonl', motion)
            observed = measure(root, expected_case=state['case_id'])
            expected_active = label in ('active_below', 'active_at', 'active_above', 'nonbeacon_sign_on')
            assert observed['reviewed_activation_complete'] == expected_active
            assert len(observed['frames_above_15_mph_in_zone']) == (301 if mph > 15 else 0)
            variants.append({'case_id': state['case_id'], 'name': label, 'active': observed['reviewed_activation_complete'],
                             'above_15_zone_frames': len(observed['frames_above_15_mph_in_zone'])})
            variant = root/suffix
            variant.mkdir()
            for name in CAMERAS:
                (variant/(name+'.mkv')).hardlink_to(root/(name+'.mkv'))
            for name in ('video_frames.jsonl', 'native_motion.jsonl', 'school_zone_context.json'):
                (variant/name).write_bytes((root/name).read_bytes())
            bundle = (Path(__file__).parent/'selected_primary' if suffix=='probe_03'
                      else Path(__file__).parent/'cases'/suffix)
            (variant/'config.json').write_bytes((bundle/'config.json').read_bytes())
            variant_roots[state['case_id']] = variant
        comparisons = []
        for name, (numbers, _, _) in SPECS.items():
            selected = {case_id(number): variant_roots[case_id(number)] for number in numbers}
            audit = compare(name, selected)
            assert audit['legal_verdict_claimed'] is False
            comparisons.append({'comparison_id': audit['comparison_id'],
                                'case_count': len(audit['case_ids']),
                                'deliberate_difference': audit['deliberate_difference']})
        pair = {case_id(number): variant_roots[case_id(number)] for number in (3, 4)}
        different = variant_roots[case_id(4)]/'school_zone_context.json'
        original = different.read_bytes()
        try:
            altered = json.loads(original)
            altered['zone_station_bounds_m'] = [49, 200]
            different.write_text(json.dumps(altered))
            try:
                compare('no_school_day', pair)
            except ValueError as exc:
                assert 'Fixed school-zone comparison condition changed' in str(exc), str(exc)
            else:
                raise AssertionError('Changed fixed school-zone bounds accepted')
            altered = json.loads(original)
            altered['school_session_day'] = True
            different.write_text(json.dumps(altered))
            try:
                compare('no_school_day', pair)
            except ValueError as exc:
                assert 'Declared school-zone exception contrast not measured' in str(exc), str(exc)
            else:
                raise AssertionError('Missing school-day contrast accepted')
        finally:
            different.write_bytes(original)
        (root/'school_zone_context.json').write_text(json.dumps(context))
        negatives = [reject(root, 'native_motion.jsonl', 'frame'),
                     reject(root, 'native_motion.jsonl', 'provenance'),
                     reject(root, 'native_motion.jsonl', 'road'),
                     reject(root, 'native_motion.jsonl', 'direction'),
                     reject(root, 'native_motion.jsonl', 'velocity'),
                     reject(root, 'school_zone_context.json', 'camera_hash'),
                     reject(root, 'school_zone_context.json', 'calendar_source'),
                     reject(root, 'school_zone_context.json', 'civil_time'),
                     reject(root, 'school_zone_context.json', 'beacon_fact'),
                     reject(root, 'school_zone_context.json', 'speed_limit'),
                     reject(root, 'school_zone_context.json', 'case'),
                     reject(root, 'school_zone_context.json', 'original_without_survey')]
        source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in root.iterdir() if p.is_file()}
        with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as derived:
            output = Path(derived)/'saved-observation.json'
            script = Path(__file__).with_name('process_saved_school_zone.py')
            command = [sys.executable, '-B', str(script), '--attempt', str(root), '--output', str(output)]
            positive = subprocess.run(command, capture_output=True, text=True)
            assert positive.returncode == 0, positive.stdout+positive.stderr
            saved = json.loads(output.read_text())
            assert saved['case_id'] == CASE and saved['sample_count'] == COUNT
            assert saved['physical_acceptance_claimed'] is False
            assert saved['legal_verdict_claimed'] is False
            missing = root/'school_zone_context.json'
            retained = missing.read_bytes()
            try:
                missing.unlink()
                negative = subprocess.run(command[:-1]+[str(Path(derived)/'missing-observation.json')],
                                          capture_output=True, text=True)
                assert negative.returncode != 0 and 'Missing saved source: school_zone_context.json' in negative.stderr
            finally:
                missing.write_bytes(retained)
            assert source_hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                     for p in root.iterdir() if p.is_file()}
        print(json.dumps({'assignment_id': AID, 'software_proof': 'synthetic_diagnostic',
                          'variants': variants, 'negative_rejections': negatives,
                          'comparison_proofs': comparisons,
                          'comparison_negative_rejections': ['fixed_zone_bounds', 'missing_school_day_difference'],
                          'saved_only': {'positive_exit_code': positive.returncode,
                                         'negative_exit_code': negative.returncode,
                                         'negative_error': 'Missing saved source: school_zone_context.json',
                                         'original_sources_unchanged': True},
                          'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()

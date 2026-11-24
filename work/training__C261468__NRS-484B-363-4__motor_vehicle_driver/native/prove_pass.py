"""Synthetic CPU diagnostics for the saved school-zone pass checker."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '.runtime-work' / 'C261468-pass-proof'
spec = importlib.util.spec_from_file_location('measure_pass', HERE / 'measure_pass.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def lines(path, rows):
    path.write_text(''.join(json.dumps(x) + '\n' for x in rows))


def rejected(name, fragment, mutate, restore):
    mutate()
    try:
        module.measure(ROOT)
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError((name, str(exc))) from exc
        answer = str(exc)
    else:
        raise AssertionError(name + ' accepted')
    finally:
        restore()
    return answer


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for camera, color in zip(module.CAMERAS, ('red', 'green', 'blue', 'yellow')):
        subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=' + color + ':s=64x48:r=20', '-frames:v', '600',
                        '-c:v', 'ffv1', str(ROOT / ('camera_' + camera + '.mkv'))], check=True)
    frame_path = ROOT / 'video_frames.jsonl'
    trace_path = ROOT / 'pass_trace.jsonl'
    context_path = ROOT / 'school_zone_context.json'
    frames = [{'video_frame': i, 'native_frame': 100 + i, 'time_s': i / 20} for i in range(600)]
    trace = [{'video_frame': i, 'native_frame': 100 + i,
              'source_kind': 'synthetic_native_sample',
              'ego_route_direction_id': 'route_A', 'other_route_direction_id': 'route_A',
              'ego_station_m': 10 + i * .28, 'other_station_m': 30 + i * .20}
             for i in range(600)]
    lines(frame_path, frames)
    lines(trace_path, trace)
    context = {'assignment_id': module.ASSIGNMENT, 'review_kind': 'synthetic_diagnostic',
               'reviewer': 'synthetic fixture', 'zone_kind': 'school_zone',
               'zone_station_m': [0, 180], 'route_direction_id': 'route_A',
               'zone_sign_source': 'synthetic fixture', 'zone_boundary_source': 'synthetic fixture',
               'route_direction_source': 'synthetic fixture', 'school_calendar_source': 'synthetic fixture',
               'operation_hours_source': 'synthetic fixture', 'civil_time_source': 'synthetic fixture',
               'beacon_or_sign_source': 'synthetic fixture',
               'school_in_session': True, 'pupils_in_class': True,
               'beacon_operational': True, 'beacon_with_sign': True, 'beacon_yellow_lights': 2,
               'beacon_yellow_alternating': True, 'sign_says_limit_in_effect': True,
               'civil_time_unix_s': 1000000, 'operation_end_unix_s': 1003600,
               'next_operation_start_unix_s': 1086400,
               'camera_sha256': {k: module.sha(ROOT / ('camera_' + k + '.mkv'))
                                 for k in module.CAMERAS}}
    write(context_path, context)
    active = module.measure(ROOT)
    assert active['pass_crossing_in_signed_zone'] and active['beacon_yellow_alternating']
    no_school = copy.deepcopy(context)
    no_school['school_in_session'] = False
    write(context_path, no_school)
    holiday = module.measure(ROOT)
    assert holiday['school_in_session'] is False and holiday['pass_crossing_video_frame'] == active['pass_crossing_video_frame']
    unlit = copy.deepcopy(context)
    unlit['beacon_yellow_alternating'] = False
    write(context_path, unlit)
    beacon_quiet = module.measure(ROOT)
    assert beacon_quiet['beacon_operational'] and not beacon_quiet['beacon_yellow_alternating']
    sign_off = copy.deepcopy(context)
    sign_off['beacon_operational'] = False
    sign_off['beacon_yellow_lights'] = None
    sign_off['beacon_with_sign'] = False
    sign_off['sign_says_limit_in_effect'] = False
    write(context_path, sign_off)
    sign_quiet = module.measure(ROOT)
    assert not sign_quiet['beacon_operational'] and not sign_quiet['sign_says_limit_in_effect']
    half_hour = copy.deepcopy(context)
    half_hour['operation_end_unix_s'] = active['civil_time_at_cross_unix_s'] - 1800
    write(context_path, half_hour)
    boundary = module.measure(ROOT)
    assert boundary['minutes_after_operation_end_at_cross'] == 30
    write(context_path, context)
    failures = {}
    failures['missing_trace'] = rejected('missing_trace', 'Missing required saved source',
        lambda: trace_path.unlink(), lambda: lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    bad[250]['native_frame'] += 1
    failures['broken_join'] = rejected('broken_join', 'does not join',
        lambda: lines(trace_path, bad), lambda: lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    bad[0]['other_route_direction_id'] = 'opposing'
    failures['opposing_route'] = rejected('opposing_route', 'same-direction route',
        lambda: lines(trace_path, bad), lambda: lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    for row in bad:
        row['ego_station_m'] = row['other_station_m'] - 10
    failures['no_pass'] = rejected('no_pass', 'No complete behind-to-ahead pass',
        lambda: lines(trace_path, bad), lambda: lines(trace_path, trace))
    bad_context = copy.deepcopy(context)
    bad_context['zone_station_m'] = [0, 20]
    failures['outside_zone'] = rejected('outside_zone', 'outside the signed school zone',
        lambda: write(context_path, bad_context), lambda: write(context_path, context))
    bad_context = copy.deepcopy(context)
    bad_context['camera_sha256']['forward'] = '0' * 64
    failures['stale_video'] = rejected('stale_video', 'not bound to original camera bytes',
        lambda: write(context_path, bad_context), lambda: write(context_path, context))
    bad_context = copy.deepcopy(context)
    bad_context['beacon_yellow_lights'] = 1
    failures['beacon_definition'] = rejected('beacon_definition', 'at least two yellow lights',
        lambda: write(context_path, bad_context), lambda: write(context_path, context))
    bad_context = copy.deepcopy(context)
    bad_context['school_calendar_source'] = ''
    failures['missing_calendar'] = rejected('missing_calendar', 'school_calendar_source',
        lambda: write(context_path, bad_context), lambda: write(context_path, context))
    bad = copy.deepcopy(trace)
    bad[0]['source_kind'] = 'original_native_pose'
    failures['wrong_provenance'] = rejected('wrong_provenance', 'source kind',
        lambda: lines(trace_path, bad), lambda: lines(trace_path, trace))
    output = {'format': 'school-zone-pass-cpu-diagnostic', 'passed': True,
              'active_crossing_frame': active['pass_crossing_video_frame'],
              'holiday_crossing_frame': holiday['pass_crossing_video_frame'],
              'beacon_quiet_observed': not beacon_quiet['beacon_yellow_alternating'],
              'sign_quiet_observed': not sign_quiet['sign_says_limit_in_effect'],
              'half_hour_elapsed_observed_min': boundary['minutes_after_operation_end_at_cross'],
              'negative_rejections': failures, 'source_kind': 'synthetic_native_sample',
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    print(json.dumps(output, indent=2))


if __name__ == '__main__':
    main()

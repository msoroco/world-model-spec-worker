"""CPU fixture and rejection proof for saved emergency-approach observations."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '.runtime-work' / 'C405647-readiness-proof'
spec = importlib.util.spec_from_file_location('measure_readiness', HERE / 'measure_readiness.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def write_lines(path, rows):
    path.write_text(''.join(json.dumps(x) + '\n' for x in rows))


def reject(name, fragment, change, restore):
    change()
    try:
        module.measure(ROOT)
    except ValueError as exc:
        assert fragment in str(exc), (name, str(exc))
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
                        '-c:v', 'ffv1', str(ROOT / (camera + '.mkv'))], check=True)
    frame_path = ROOT / 'video_frames.jsonl'
    trace_path = ROOT / 'approach_trace.jsonl'
    review_path = ROOT / 'emergency_review.json'
    frames = [{'video_frame': i, 'native_frame': 30 + i, 'time_s': i / 20} for i in range(600)]
    trace = [{'video_frame': i, 'native_frame': 30 + i,
              'source_kind': 'synthetic_native_sample',
              'ego_speed_mps': max(0, 15 - max(0, i - 55) * .1),
              'emergency_speed_mps': 2,
              'surface_gap_m': 80 - .07 * i,
              'ego_brake': 1 if i >= 55 and i < 205 else 0,
              'emergency_flashing_visible': i >= 50,
              'emergency_motion_visible': i >= 50,
              'hand_signal_visible': False} for i in range(600)]
    review = {'assignment_id': module.ASSIGNMENT, 'review_kind': 'synthetic_diagnostic',
              'reviewer': 'synthetic fixture', 'vehicle_class': 'authorized_emergency_vehicle',
              'vehicle_class_source': 'synthetic fixture', 'flashing_light_source': 'synthetic fixture',
              'visible_motion_source': 'synthetic fixture', 'officer_direction_source': 'synthetic fixture',
              'lights_meet_484A_480_3': True, 'visible_to_approaching_driver': True,
              'officer_direction_present': False,
              'camera_sha256': {camera: module.sha(ROOT / (camera + '.mkv'))
                                for camera in module.CAMERAS}}
    write_lines(frame_path, frames)
    write_lines(trace_path, trace)
    write(review_path, review)
    response = module.measure(ROOT)
    assert response['trigger_frame'] == 50 and response['first_brake_frame'] == 55
    assert response['brake_delay_s'] == .25 and response['stopped_frame'] == 205
    assert response['braked_approaching_frame_count'] > 0
    assert response['application_review_state'] == 'qualifying_indication_reviewed'
    assert 'vehicle_moving' in response['indication_kinds_at_trigger']
    hand_trace = copy.deepcopy(trace)
    for row in hand_trace:
        row['emergency_speed_mps'] = 0
        row['emergency_motion_visible'] = False
        row['hand_signal_visible'] = row['video_frame'] >= 50
    hand_review = copy.deepcopy(review)
    hand_review['hand_signal_source'] = 'synthetic hand-signal fixture'
    write_lines(trace_path, hand_trace)
    write(review_path, hand_review)
    hand_response = module.measure(ROOT)
    assert hand_response['trigger_frame'] == 50
    assert hand_response['indication_kinds_at_trigger'] == ['visible_driver_hand_signal']
    absent_hand_source = copy.deepcopy(hand_review)
    absent_hand_source.pop('hand_signal_source')
    hand_source_error = reject('missing_hand_source', 'hand_signal_source',
        lambda: write(review_path, absent_hand_source),
        lambda: write(review_path, hand_review))
    officer_review = copy.deepcopy(hand_review)
    officer_review['officer_direction_present'] = True
    write(review_path, officer_review)
    officer_response = module.measure(ROOT)
    assert officer_response['application_review_state'] == 'officer_direction_exception'
    unqualified_review = copy.deepcopy(hand_review)
    unqualified_review['lights_meet_484A_480_3'] = False
    write(review_path, unqualified_review)
    unqualified_response = module.measure(ROOT)
    assert unqualified_response['application_review_state'] == 'light_qualification_pending_or_negative'
    write(review_path, review)
    write_lines(trace_path, trace)
    no_brake = copy.deepcopy(trace)
    for row in no_brake:
        row['ego_speed_mps'] = 15
        row['ego_brake'] = 0
    write_lines(trace_path, no_brake)
    absent = module.measure(ROOT)
    assert absent['first_brake_frame'] is None and absent['stopped_frame'] is None
    assert absent['braked_approaching_frame_count'] == 0
    write_lines(trace_path, trace)
    failures = {'missing_hand_source': hand_source_error}
    failures['missing_trace'] = reject('missing_trace', 'Missing required saved source',
        lambda: trace_path.unlink(), lambda: write_lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    bad[50]['native_frame'] += 1
    failures['frame_join'] = reject('frame_join', 'does not join',
        lambda: write_lines(trace_path, bad), lambda: write_lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    for row in bad:
        row['emergency_flashing_visible'] = False
    failures['no_flashing'] = reject('no_flashing', 'No frame-bound flashing',
        lambda: write_lines(trace_path, bad), lambda: write_lines(trace_path, trace))
    bad = copy.deepcopy(trace)
    for row in bad:
        row['surface_gap_m'] = 80
    failures['no_approach'] = reject('no_approach', 'No measured approach',
        lambda: write_lines(trace_path, bad), lambda: write_lines(trace_path, trace))
    bad_review = copy.deepcopy(review)
    bad_review['camera_sha256']['overview'] = '0' * 64
    failures['stale_video'] = reject('stale_video', 'not bound',
        lambda: write(review_path, bad_review), lambda: write(review_path, review))
    bad_review = copy.deepcopy(review)
    bad_review['vehicle_class'] = 'ordinary_vehicle'
    failures['wrong_class'] = reject('wrong_class', 'Qualifying vehicle class',
        lambda: write(review_path, bad_review), lambda: write(review_path, review))
    bad_review = copy.deepcopy(review)
    bad_review['visible_to_approaching_driver'] = False
    failures['not_visible'] = reject('not_visible', 'not independently reviewed as visible',
        lambda: write(review_path, bad_review), lambda: write(review_path, review))
    bad_review = copy.deepcopy(review)
    bad_review['flashing_light_source'] = ''
    failures['unsourced_lights'] = reject('unsourced_lights', 'flashing_light_source',
        lambda: write(review_path, bad_review), lambda: write(review_path, review))
    bad = copy.deepcopy(trace)
    bad[0]['source_kind'] = 'original_native_motion'
    failures['wrong_provenance'] = reject('wrong_provenance', 'source kind',
        lambda: write_lines(trace_path, bad), lambda: write_lines(trace_path, trace))
    print(json.dumps({'format':'emergency-readiness-cpu-diagnostic', 'passed': True,
        'trigger_frame':response['trigger_frame'], 'brake_delay_s':response['brake_delay_s'],
        'stop_distance_m':response['observed_stop_distance_m'],
        'unbraked_first_brake':absent['first_brake_frame'],
        'hand_signal_trigger_frame':hand_response['trigger_frame'],
        'officer_direction_review_state':officer_response['application_review_state'],
        'unqualified_light_review_state':unqualified_response['application_review_state'],
        'negative_rejections':failures, 'source_kind':'synthetic_native_sample',
        'physical_acceptance_claimed':False, 'legal_verdict_claimed':False}, indent=2))


if __name__ == '__main__':
    main()

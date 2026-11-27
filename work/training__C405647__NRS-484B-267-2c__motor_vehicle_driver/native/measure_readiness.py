"""Saved-source emergency approach and brake-response observations.

No observed proxy is a legal definition of "prepared to stop".
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ASSIGNMENT = 'training__C405647__NRS-484B-267-2c__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERA_DIMENSIONS = {
    'overview': (1920, 1080),
    'approach': (1280, 720),
    'reference_corner': (1280, 720),
    'driver_reference': (1280, 720),
}
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def measure(root):
    root = Path(root)
    frame_path = root / 'video_frames.jsonl'
    trace_path = root / 'approach_trace.jsonl'
    review_path = root / 'emergency_review.json'
    for path in (frame_path, trace_path, review_path):
        if not path.is_file():
            raise ValueError('Missing required saved source: ' + path.name)
    frames, trace = lines(frame_path), lines(trace_path)
    review = json.loads(review_path.read_text())
    if len(frames) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Requires all 600 original 20 Hz samples')
    video_hashes = {}
    for camera in CAMERAS:
        path = root / (camera + '.mkv')
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing nonempty source camera: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
                                '-of', 'json', str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(FRAMES) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + camera)
        video_hashes[camera] = sha(path)
    if review.get('camera_sha256') != video_hashes:
        raise ValueError('Emergency review is not bound to source camera bytes')
    if review.get('assignment_id') != ASSIGNMENT:
        raise ValueError('Emergency review assignment mismatch')
    if review.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Review provenance kind missing')
    if review['review_kind'] == 'original_source_review':
        for camera in CAMERAS:
            probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                    '-show_entries', 'stream=width,height', '-of', 'json',
                                    str(root / (camera + '.mkv'))],
                                   capture_output=True, text=True, check=True)
            dim = json.loads(probe.stdout)['streams'][0]
            if (dim['width'], dim['height']) != CAMERA_DIMENSIONS[camera]:
                raise ValueError('Original source camera differs from exact capture profile: ' + camera)
    for key in ('reviewer', 'vehicle_class_source', 'flashing_light_source',
                'visible_motion_source', 'officer_direction_source'):
        if not review.get(key):
            raise ValueError('Missing independent reviewed context source: ' + key)
    if review.get('vehicle_class') not in ('authorized_emergency_vehicle', 'regulatory_agency_official_vehicle'):
        raise ValueError('Qualifying vehicle class unconfirmed')
    for key in ('lights_meet_484A_480_3', 'visible_to_approaching_driver', 'officer_direction_present'):
        if type(review.get(key)) is not bool:
            raise ValueError('Missing reviewed condition: ' + key)
    previous_native, previous_time = -1, -1.0
    speeds, gaps, brakes, moving, lights, motion_visible, hand_visible, times = [], [], [], [], [], [], [], []
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_native:
            raise ValueError('Original frame identity invalid')
        if not finite(t) or t <= previous_time or (i and abs(t - previous_time - .05) > .005):
            raise ValueError('Original 20 Hz cadence invalid')
        if row.get('video_frame') != i or row.get('native_frame') != native:
            raise ValueError('Approach trace does not join original frame map')
        source_kind = 'synthetic_native_sample' if review['review_kind'] == 'synthetic_diagnostic' else 'original_native_motion'
        if row.get('source_kind') != source_kind:
            raise ValueError('Motion source kind does not match review kind')
        for key in ('ego_speed_mps', 'emergency_speed_mps', 'surface_gap_m', 'ego_brake'):
            if not finite(row.get(key)) or row[key] < 0:
                raise ValueError('Missing nonnegative Native measurement: ' + key)
        if row['ego_brake'] > 1:
            raise ValueError('Brake control outside normalized range')
        for key in ('emergency_flashing_visible', 'emergency_motion_visible', 'hand_signal_visible'):
            if type(row.get(key)) is not bool:
                raise ValueError('Missing frame-bound visibility: ' + key)
        speeds.append(row['ego_speed_mps'])
        gaps.append(row['surface_gap_m'])
        brakes.append(row['ego_brake'])
        moving.append(row['emergency_speed_mps'])
        lights.append(row['emergency_flashing_visible'])
        motion_visible.append(row['emergency_motion_visible'])
        hand_visible.append(row['hand_signal_visible'])
        times.append(t)
        previous_native, previous_time = native, t
    if times[-1] - times[0] < 29.9:
        raise ValueError('Original sample span less than 30 seconds')
    if gaps[0] <= min(gaps) or not any(gaps[i] < gaps[i-1] for i in range(1, FRAMES)):
        raise ValueError('No measured approach to qualifying vehicle')
    trigger = next((i for i in range(FRAMES) if lights[i] and (moving[i] > 0 or motion_visible[i] or hand_visible[i])), None)
    if trigger is None:
        raise ValueError('No frame-bound flashing and moving/preparing indication')
    if not review['visible_to_approaching_driver']:
        raise ValueError('Qualifying indication not independently reviewed as visible')
    indication_kinds = []
    if moving[trigger] > 0:
        indication_kinds.append('vehicle_moving')
    if motion_visible[trigger]:
        indication_kinds.append('visible_movement')
    if hand_visible[trigger]:
        indication_kinds.append('visible_driver_hand_signal')
    if not indication_kinds:
        raise ValueError('No reviewed moving or preparing indication at trigger')
    if hand_visible[trigger] and not review.get('hand_signal_source'):
        raise ValueError('Missing independent reviewed hand_signal_source')
    brake = next((i for i in range(trigger, FRAMES) if brakes[i] > 0), None)
    stopped = next((i for i in range(trigger, FRAMES) if speeds[i] == 0), None)
    decels = [(speeds[i-1] - speeds[i]) / (times[i] - times[i-1]) for i in range(trigger+1, FRAMES)]
    approaching = [i for i in range(trigger + 1, FRAMES) if gaps[i] < gaps[i - 1]]
    braked_while_approaching = sum(brakes[i] > 0 for i in approaching)
    return {
        'format': 'saved-emergency-approach-observation', 'assignment_id': ASSIGNMENT,
        'source_kind': review['review_kind'],
        'sources': {'video_frames.jsonl': sha(frame_path), 'approach_trace.jsonl': sha(trace_path),
                    'emergency_review.json': sha(review_path),
                    **{camera + '.mkv': h for camera, h in video_hashes.items()}},
        'sample_count': FRAMES, 'sample_span_s': times[-1] - times[0],
        'trigger_frame': trigger, 'trigger_time_s': times[trigger],
        'trigger_gap_m': gaps[trigger], 'trigger_ego_speed_mps': speeds[trigger],
        'indication_kinds_at_trigger': indication_kinds,
        'statutory_light_qualification_reviewed': review['lights_meet_484A_480_3'],
        'officer_direction_exception_reviewed': review['officer_direction_present'],
        'application_review_state': ('officer_direction_exception' if review['officer_direction_present']
                                     else 'light_qualification_pending_or_negative' if not review['lights_meet_484A_480_3']
                                     else 'qualifying_indication_reviewed'),
        'emergency_moving_at_trigger': moving[trigger] > 0,
        'emergency_motion_visible_at_trigger': motion_visible[trigger],
        'hand_signal_visible_at_trigger': hand_visible[trigger],
        'flashing_visible_at_trigger': lights[trigger],
        'lights_meet_484A_480_3_reviewed': review['lights_meet_484A_480_3'],
        'officer_direction_present_reviewed': review['officer_direction_present'],
        'first_brake_frame': brake, 'brake_delay_s': None if brake is None else times[brake] - times[trigger],
        'approaching_frame_count_after_trigger': len(approaching),
        'braked_approaching_frame_count': braked_while_approaching,
        'braked_approach_fraction': None if not approaching else braked_while_approaching / len(approaching),
        'stopped_frame': stopped, 'observed_stop_distance_m': None if stopped is None else sum(speeds[i] * (times[i+1]-times[i]) for i in range(trigger, stopped)),
        'peak_observed_deceleration_mps2': max(decels), 'minimum_surface_gap_m': min(gaps),
        'measurement_note':'Brake and stopping measurements are engineering observations, not a legal threshold for prepared to stop.',
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    Path(args.output_json).write_text(json.dumps(measure(args.source_dir), indent=2) + '\n')

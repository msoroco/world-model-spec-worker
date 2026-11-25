"""Saved-only school-bus speed measurement from sealed Native sources.

This reports observations and context, not a legal or physical verdict. A human
review of the passenger footage and trip purpose is a separate required source.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

MPH_PER_MPS = 1 / 0.44704
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def measure(root):
    root = Path(root)
    frame_path = root / 'video_frames.jsonl'
    motion_path = root / 'bus_motion.jsonl'
    review_path = root / 'passenger_trip_review.json'
    for path in (frame_path, motion_path, review_path):
        if not path.is_file():
            raise ValueError('Missing required saved source: ' + path.name)
    frames = read_jsonl(frame_path)
    motion = read_jsonl(motion_path)
    review = read_json(review_path)
    if len(frames) != FRAMES or len(motion) != FRAMES:
        raise ValueError('Requires all 600 original 20 Hz samples')
    video_hashes = {}
    for camera in CAMERAS:
        path = root / (camera + '.mkv')
        if not path.is_file() or path.stat().st_size == 0:
            raise ValueError('Missing nonempty original camera: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
                                '-of', 'json', str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('Camera decode failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(FRAMES) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Camera must decode all 600 frames at 20 Hz: ' + camera)
        video_hashes[camera] = sha(path)
    if review.get('camera_sha256') != video_hashes:
        raise ValueError('Passenger review is not bound to all original camera bytes')
    if review.get('assignment_id') != 'training__C230241__NRS-484B-360-1__school_bus_driver':
        raise ValueError('Passenger review assignment mismatch')
    if not review.get('bus_blueprint') or review.get('school_bus_confirmed') is not True:
        raise ValueError('School-bus identity not confirmed')
    if (not review.get('reviewer') or review.get('trip_purpose') != 'transporting pupils to or from school'
            or not review.get('trip_purpose_source')):
        raise ValueError('Missing independently reviewed school trip purpose')
    if (review.get('pupils_aboard') is not True or not review.get('pupil_evidence_frames')
            or type(review.get('observed_pupil_count')) is not int or review['observed_pupil_count'] < 1):
        raise ValueError('Pupils aboard not reviewed from retained camera source')
    sample_frames = review['pupil_evidence_frames']
    if any(type(f) is not int or f < 0 or f >= FRAMES for f in sample_frames):
        raise ValueError('Passenger review frame out of range')
    if review.get('review_kind') not in ('synthetic_diagnostic', 'original_video_review'):
        raise ValueError('Passenger review kind missing')
    if review['review_kind'] == 'original_video_review':
        for camera in CAMERAS:
            stream = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                     '-show_entries', 'stream=width,height', '-of', 'json',
                                     str(root / (camera + '.mkv'))],
                                    capture_output=True, text=True, check=True)
            dimensions = json.loads(stream.stdout)['streams'][0]
            if (dimensions['width'], dimensions['height']) != ((1920, 1080) if camera == 'overview' else (1280, 720)):
                raise ValueError('Original camera profile must be full resolution: ' + camera)
    speeds = []
    previous_native = -1
    previous_time = -1.0
    for i, (frame, row) in enumerate(zip(frames, motion)):
        native = frame.get('native_frame')
        t = frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= previous_native:
            raise ValueError('Original video/native frame join invalid')
        if not finite(t) or t <= previous_time:
            raise ValueError('Original frame time invalid')
        if i and abs((t - previous_time) - .05) > .005:
            raise ValueError('Original sample cadence not 20 Hz')
        if row.get('native_frame') != native or row.get('video_frame') != i:
            raise ValueError('Bus motion does not join original frame map')
        velocity = row.get('velocity_mps')
        if not isinstance(velocity, list) or len(velocity) != 3 or not all(finite(v) for v in velocity):
            raise ValueError('Missing finite original bus velocity')
        expected_source = ('synthetic_native_sample' if review['review_kind'] == 'synthetic_diagnostic'
                           else 'original_native_velocity')
        if row.get('source_kind') != expected_source:
            raise ValueError('Bus velocity source kind does not match review kind')
        speeds.append(math.sqrt(sum(v * v for v in velocity)) * MPH_PER_MPS)
        previous_native, previous_time = native, t
    if previous_time - frames[0]['time_s'] < 29.9:
        raise ValueError('Original sample span is less than 30 seconds')
    return {
        'format': 'school-bus-saved-speed-measurement',
        'assignment_id': review['assignment_id'],
        'source_kind': review['review_kind'],
        'sources': {'video_frames.jsonl': sha(frame_path), 'bus_motion.jsonl': sha(motion_path),
                    'passenger_trip_review.json': sha(review_path),
                    **{'camera_' + k + '.mkv': v for k, v in video_hashes.items()}},
        'sample_count': FRAMES, 'sample_span_s': previous_time - frames[0]['time_s'],
        'maximum_observed_mph': max(speeds),
        'frames_above_55_mph': [i for i, v in enumerate(speeds) if v > 55],
        'measurement_note': '55 mph is statutory text; no tolerance or legal conclusion is inferred.',
        'pupils_aboard_reviewed': True, 'observed_pupil_count': review['observed_pupil_count'],
        'reviewer': review['reviewer'],
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    result = measure(args.source_dir)
    Path(args.output_json).write_text(json.dumps(result, indent=2) + '\n')

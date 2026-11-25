"""CPU diagnostic for the saved-source school-bus speed measurement."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / '.runtime-work' / 'school-bus-speed-proof'
spec = importlib.util.spec_from_file_location('measure_speed', HERE / 'measure_speed.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def expect_error(name, fragment, mutate):
    mutate()
    try:
        module.measure(ROOT)
    except ValueError as exc:
        assert fragment in str(exc), (name, str(exc))
        return str(exc)
    raise AssertionError(name + ' was accepted')


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for camera, color in zip(module.CAMERAS, ('red', 'green', 'blue', 'yellow')):
        path = ROOT / (camera + '.mkv')
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i',
                        'color=c=' + color + ':s=64x48:r=20', '-frames:v', '600',
                        '-c:v', 'ffv1', str(path)], check=True)
    frame_path = ROOT / 'video_frames.jsonl'
    motion_path = ROOT / 'bus_motion.jsonl'
    frame_path.write_text(''.join(json.dumps({'video_frame': i, 'native_frame': 40 + i,
                                              'time_s': i / 20}) + '\n' for i in range(600)))
    def motion(speed):
        return ''.join(json.dumps({'video_frame': i, 'native_frame': 40 + i,
                                   'velocity_mps': [speed / module.MPH_PER_MPS, 0, 0],
                                   'source_kind': 'synthetic_native_sample'}) + '\n'
                       for i in range(600))
    motion_path.write_text(motion(54))
    review = {'assignment_id': 'training__C230241__NRS-484B-360-1__school_bus_driver',
              'review_kind': 'synthetic_diagnostic', 'reviewer': 'synthetic fixture',
              'bus_blueprint': 'diagnostic_school_bus_asset', 'school_bus_confirmed': True,
              'trip_purpose': 'transporting pupils to or from school',
              'trip_purpose_source': 'synthetic diagnostic context',
              'pupils_aboard': True, 'observed_pupil_count': 3,
              'pupil_evidence_frames': [0, 300, 599],
              'camera_sha256': {camera: module.sha(ROOT / (camera + '.mkv'))
                                for camera in module.CAMERAS}}
    review_path = ROOT / 'passenger_trip_review.json'
    write(review_path, review)
    below = module.measure(ROOT)
    assert below['maximum_observed_mph'] < 55 and not below['frames_above_55_mph']
    motion_path.write_text(motion(56))
    above = module.measure(ROOT)
    assert above['maximum_observed_mph'] > 55 and len(above['frames_above_55_mph']) == 600
    failures = {}
    original_motion = motion_path.read_text()
    failures['missing_motion'] = expect_error('missing_motion', 'Missing required saved source', lambda: motion_path.unlink())
    motion_path.write_text(original_motion)
    altered = original_motion.replace('"native_frame": 340', '"native_frame": 341', 1)
    failures['bad_join'] = expect_error('bad_join', 'does not join', lambda: motion_path.write_text(altered))
    motion_path.write_text(original_motion)
    bad_review = copy.deepcopy(review)
    bad_review['pupils_aboard'] = False
    failures['no_pupils'] = expect_error('no_pupils', 'Pupils aboard', lambda: write(review_path, bad_review))
    write(review_path, review)
    bad_review = copy.deepcopy(review)
    bad_review['camera_sha256']['overview'] = '0' * 64
    failures['stale_video'] = expect_error('stale_video', 'not bound', lambda: write(review_path, bad_review))
    write(review_path, review)
    bad_motion = original_motion.replace('synthetic_native_sample', 'original_native_velocity', 1)
    failures['source_kind'] = expect_error('source_kind', 'source kind', lambda: motion_path.write_text(bad_motion))
    motion_path.write_text(original_motion)
    motion_path.write_text(''.join(original_motion.splitlines(True)[:-1]))
    failures['short_motion'] = expect_error('short_motion', 'all 600', lambda: None)
    motion_path.write_text(original_motion)
    result = {'format': 'school-bus-speed-diagnostic', 'passed': True,
              'positive_below_mph': below['maximum_observed_mph'],
              'positive_above_mph': above['maximum_observed_mph'],
              'negative_rejections': failures,
              'source_kind': 'synthetic_native_sample',
              'physical_acceptance_claimed': False}
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

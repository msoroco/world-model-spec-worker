"""Independent original-source audit for the exact officer-direction cases."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PREFIX = 'heldout__C10365__NRS-484B-100__motor_vehicle_driver__'
CASES = {'stop_responds', 'stop_does_not_respond',
         'proceed_responds', 'proceed_does_not_respond'}
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def audit(case: str, attempt: Path) -> dict:
    slug = case.removeprefix(PREFIX)
    if case != PREFIX + slug or slug not in CASES:
        raise ValueError('Wrong exact delivery case')
    attempt = Path(attempt)

    def source(name):
        path = attempt / name
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing required source: ' + name)
        return path

    def rows(name):
        return [json.loads(line) for line in source(name).read_text().splitlines() if line.strip()]

    context = json.loads(source('officer_context.json').read_text())
    direction = json.loads(source('officer_direction.json').read_text())
    motion = json.loads(source('subject_motion.json').read_text())['frames']
    history = rows('subject_motion_history.jsonl')
    trace = rows('trace.jsonl')
    frames = rows('video_frames.jsonl')
    if not history or history != motion or len(history) != len(trace) or len(trace) != len(frames):
        raise ValueError('Original participant/time join incomplete')
    if context.get('actor_role') != 'motor_vehicle_driver' or context.get('officer_role') != 'police_officer':
        raise ValueError('Original officer/subject identity incomplete')
    if direction.get('officer_id') != context.get('officer_id') or direction.get('subject_id') != context.get('subject_id'):
        raise ValueError('Original officer/subject identity incomplete')
    if direction.get('command') != ('stop' if slug.startswith('stop_') else 'proceed'):
        raise ValueError('Original command differs from exact case')
    for index, (h, t, frame) in enumerate(zip(history, trace, frames)):
        if (h.get('frame') != t.get('frame') or h.get('frame') != frame.get('carla_frame')
                or frame.get('video_frame') != index or h.get('subject_id') != context.get('subject_id')
                or h.get('time_s') != t.get('time_s') or t.get('time_s') != frame.get('time_s')):
            raise ValueError('Original participant/time join incomplete')
    if direction.get('frame') not in {h['frame'] for h in history}:
        raise ValueError('Original direction frame missing from capture')
    result = json.loads(source('result.json').read_text())
    if result.get('case_id') != case or result.get('legal_acceptance_claimed') or result.get('physical_acceptance_claimed'):
        raise ValueError('Wrong case or unsupported acceptance claim')
    if (result.get('trace_reference') != 'trace.jsonl'
            or result.get('video_frame_map_reference') != 'video_frames.jsonl'
            or result.get('video_references') != list(CAMERAS)):
        raise ValueError('Original source references changed')
    decoded = {}
    for camera in CAMERAS:
        media = source(camera)
        completed = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(media), '-f', 'null', '-'],
                                   capture_output=True, text=True)
        if completed.returncode:
            raise ValueError('Full video decode failed: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries', 'stream=nb_read_frames',
                                '-of', 'default=noprint_wrappers=1:nokey=1', str(media)],
                               capture_output=True, text=True, check=True)
        try:
            count = int(probe.stdout.strip())
        except ValueError as exc:
            raise ValueError('Full video frame count unavailable: ' + camera) from exc
        if count != len(frames):
            raise ValueError('Full video frame count changed: ' + camera)
        decoded[camera] = count
    names = ('officer_context.json', 'officer_direction.json', 'subject_motion.json',
             'subject_motion_history.jsonl', 'trace.jsonl', 'video_frames.jsonl')
    return {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
            'source_frames': len(frames), 'video_frames': decoded,
            'source_sha256': {name: hashlib.sha256(source(name).read_bytes()).hexdigest() for name in names},
            'physical_completion_check': bool(result.get('setup_confirmed') and result.get('maneuver_completed')
                                              and not result.get('physical_failure_flags')),
            'actual_pixels_check': 'Full codec decode and frame count; original gesture/body visibility requires physical review',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, Path(args.attempt)), indent=2))


if __name__ == '__main__':
    main()

"""Independent CPU source audit for prospective C229126 saved attempts.

This verifies original source presence, joins, and full camera decodes. A real
Native attempt still needs physical and pixel review before acceptance.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


PREFIX = 'heldout__C229126__NRS-484B-207-1__motor_vehicle_driver__'
SUFFIXES = {'left_pass_wide', 'left_pass_narrow', 'return_before_clear',
            'return_after_clear'}
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _read(path):
    if not path.is_file():
        raise ValueError(f'Missing original source: {path.name}')
    return path.read_bytes()


def _rows(path):
    return [json.loads(line) for line in _read(path).decode().splitlines()
            if line.strip()]


def _decode(path):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
         '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height',
         '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError(f'Original camera stream absent: {path.name}')
    stream = streams[0]
    frames = int(stream.get('nb_read_frames', 0))
    if frames <= 0 or int(stream['width']) <= 0 or int(stream['height']) <= 0:
        raise ValueError(f'Original camera frames absent: {path.name}')
    subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
                    '-map', '0:v:0', '-f', 'null', '-'], capture_output=True,
                   check=True)
    return frames, [int(stream['width']), int(stream['height'])]


def audit(attempt, case_id):
    if not case_id.startswith(PREFIX) or case_id[len(PREFIX):] not in SUFFIXES:
        raise ValueError('Wrong exact C229126 delivery case')
    attempt = Path(attempt)
    config = json.loads(_read(attempt / 'config.json'))
    if (config.get('selected_case_id'), config.get('law_id'),
            config.get('cell_id'), config.get('actor')) != (
            case_id, 'NRS-484B-207-1', 'C229126', 'motor_vehicle_driver'):
        raise ValueError('Original delivery config identity changed')
    frames = _rows(attempt / 'video_frames.jsonl')
    trace = _rows(attempt / 'trace.jsonl')
    bodies = _rows(attempt / 'participant_footprints.jsonl')
    if not frames or not trace or not bodies:
        raise ValueError('Original frame, trace and body sources required')
    ids = [row['native_frame'] for row in frames]
    if [row['video_frame'] for row in frames] != list(range(len(frames))):
        raise ValueError('Original video frame order changed')
    if ids != sorted(set(ids)) or ids != [row['frame'] for row in trace] or ids != [row['frame'] for row in bodies]:
        raise ValueError('Original source frame join changed')
    times = [row['time_s'] for row in frames]
    if times != [row['time_s'] for row in trace] or times != [row['time_s'] for row in bodies]:
        raise ValueError('Original source timestamp join changed')
    participants = {(row.get('ego_id'), row.get('other_id')) for row in bodies}
    if len(participants) != 1 or any(not value for value in next(iter(participants))):
        raise ValueError('All original participants required')
    for row in bodies:
        if len(row.get('ego_corners', [])) != 4 or len(row.get('other_corners', [])) != 4:
            raise ValueError('Original four-corner body evidence required')
    camera_sources = {}
    for name in CAMERAS:
        path = attempt / (name + '.mkv')
        _read(path)
        count, size = _decode(path)
        if count != len(frames):
            raise ValueError(f'Original camera frame count changed: {name}')
        camera_sources[name] = {'sha256': sha256(path.read_bytes()).hexdigest(),
                                'frames': count, 'dimensions': size}
    return {'format': 'worker-c229126-delivery-source-audit',
            'case_id': case_id, 'frame_count': len(ids),
            'participant_ids': list(next(iter(participants))),
            'frame_map_sha256': sha256(_read(attempt / 'video_frames.jsonl')).hexdigest(),
            'trace_sha256': sha256(_read(attempt / 'trace.jsonl')).hexdigest(),
            'body_sha256': sha256(_read(attempt / 'participant_footprints.jsonl')).hexdigest(),
            'camera_sources': camera_sources,
            'source_checks_passed': True, 'actual_pixel_visibility_verified': False,
            'physical_completion_verified': False, 'legal_acceptance_claimed': False}


def selftest(attempt, case_id):
    result = audit(attempt, case_id)
    with tempfile.TemporaryDirectory() as temp:
        changed = Path(temp) / 'attempt'
        shutil.copytree(attempt, changed)
        (changed / 'participant_footprints.jsonl').unlink()
        try:
            audit(changed, case_id)
        except ValueError as error:
            assert 'Missing original source' in str(error)
        else:
            raise AssertionError('Missing original body source accepted')
        shutil.copy2(Path(attempt) / 'participant_footprints.jsonl',
                     changed / 'participant_footprints.jsonl')
        (changed / 'approach.mkv').unlink()
        try:
            audit(changed, case_id)
        except ValueError as error:
            assert 'Missing original source' in str(error)
        else:
            raise AssertionError('Missing original camera accepted')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    result = (selftest if args.selftest else audit)(args.attempt, args.case)
    print(json.dumps(result, indent=2))

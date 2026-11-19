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


def compare(baseline, variant, comparison_id):
    """Reopen both original source sets and test one controlled difference."""
    pairs = {
        'left_pass_clearance': ('left_pass_wide', 'left_pass_narrow'),
        'return_clearance_order': ('return_before_clear', 'return_after_clear'),
    }
    if comparison_id not in pairs:
        raise ValueError('Unknown C229126 comparison')
    first, second = pairs[comparison_id]
    baseline, variant = Path(baseline), Path(variant)
    left_audit = audit(baseline, PREFIX + first)
    right_audit = audit(variant, PREFIX + second)
    fixed_names = ('road.xodr', 'alley_context.json', 'trace.jsonl',
                   'video_frames.jsonl') + tuple(name + '.mkv' for name in CAMERAS)
    fixed = {}
    for name in fixed_names:
        left_hash = sha256(_read(baseline / name)).hexdigest()
        right_hash = sha256(_read(variant / name)).hexdigest()
        if left_hash != right_hash:
            raise ValueError('Controlled comparison changed fixed source: ' + name)
        fixed[name] = left_hash
    a = _rows(baseline / 'participant_footprints.jsonl')
    b = _rows(variant / 'participant_footprints.jsonl')
    if len(a) != len(b) or len(a) != left_audit['frame_count'] or len(b) != right_audit['frame_count']:
        raise ValueError('Controlled comparison frame count changed')
    for x, y in zip(a, b):
        for name in ('frame', 'time_s', 'ego_id', 'other_id', 'other_corners',
                     'ego_heading_xy', 'other_heading_xy', 'road_tangent_xy',
                     'road_id', 'other_lane_id', 'other_speed_mps'):
            if x.get(name) != y.get(name):
                raise ValueError('Controlled comparison changed fixed body source: ' + name)
        if [p[0] for p in x['ego_corners']] != [p[0] for p in y['ego_corners']]:
            raise ValueError('Controlled comparison changed longitudinal motion')

    def measured(rows):
        def extents(row, actor, axis):
            points = [point[axis] for point in row[actor + '_corners']]
            return min(points), max(points)
        abreast = []
        first_abreast = None
        for index, row in enumerate(rows):
            ego_x, other_x = extents(row, 'ego', 0), extents(row, 'other', 0)
            if ego_x[1] >= other_x[0] and other_x[1] >= ego_x[0]:
                first_abreast = index if first_abreast is None else first_abreast
                ego_y, other_y = extents(row, 'ego', 1), extents(row, 'other', 1)
                abreast.append(ego_y[0] - other_y[1])
        if first_abreast is None:
            raise ValueError('Controlled comparison lacks an abreast interval')
        def center(row):
            return sum(point[1] for point in row['ego_corners']) / len(row['ego_corners'])
        returns = [i for i in range(first_abreast + 1, len(rows))
                   if center(rows[i]) < center(rows[i-1]) - .1]
        if not returns:
            raise ValueError('Controlled comparison lacks a rightward return')
        at = rows[returns[0]]
        ego_x, other_x = extents(at, 'ego', 0), extents(at, 'other', 0)
        return {'minimum_abreast_left_gap_m': min(abreast),
                'first_return_frame': at['frame'],
                'body_clearance_at_first_return_m': ego_x[0] - other_x[1]}

    left, right = measured(a), measured(b)
    if comparison_id == 'left_pass_clearance':
        if not (left['minimum_abreast_left_gap_m'] > right['minimum_abreast_left_gap_m']
                and left['first_return_frame'] == right['first_return_frame']):
            raise ValueError('Left-pass clearance comparison lacks intended difference')
    else:
        early = next(i for i, row in enumerate(a) if row['frame'] == left['first_return_frame'])
        if any(a[i]['ego_corners'] != b[i]['ego_corners'] for i in range(early)):
            raise ValueError('Return comparison changed pre-return left pass')
        if not (left['first_return_frame'] < right['first_return_frame']
                and left['body_clearance_at_first_return_m'] < 0
                and right['body_clearance_at_first_return_m'] > 0):
            raise ValueError('Return clearance comparison lacks intended difference')
    return {'format': 'worker-c229126-controlled-source-comparison',
            'comparison_id': comparison_id, 'case_ids': [PREFIX + first, PREFIX + second],
            'fixed_source_sha256': fixed,
            'body_source_sha256': [sha256(_read(baseline / 'participant_footprints.jsonl')).hexdigest(),
                                   sha256(_read(variant / 'participant_footprints.jsonl')).hexdigest()],
            'measured': {'baseline': left, 'variant': right},
            'fixed_conditions_passed': True, 'intended_difference_passed': True,
            'actual_native_capture': False, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


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
    parser.add_argument('--attempt')
    parser.add_argument('--case')
    parser.add_argument('--baseline')
    parser.add_argument('--variant')
    parser.add_argument('--comparison', choices=['left_pass_clearance', 'return_clearance_order'])
    parser.add_argument('--selftest', action='store_true')
    args = parser.parse_args()
    if args.comparison:
        if not args.baseline or not args.variant or args.attempt or args.case or args.selftest:
            parser.error('Comparison requires --baseline and --variant only')
        result = compare(args.baseline, args.variant, args.comparison)
    else:
        if not args.attempt or not args.case or args.baseline or args.variant:
            parser.error('Source audit requires --attempt and --case only')
        result = (selftest if args.selftest else audit)(args.attempt, args.case)
    print(json.dumps(result, indent=2))

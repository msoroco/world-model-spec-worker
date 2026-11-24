"""Source-only taxi-stand measurement; no designation or legal verdict."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

from check import check
from request import FRAMES, RATE

CAMERAS = ('overview', 'approach', 'first_intersection', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def media(path):
    if not path.is_file():
        raise ValueError('Missing source camera: ' + path.name)
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                             '-select_streams', 'v:0', '-show_entries',
                             'stream=codec_name,nb_read_frames', '-of', 'json',
                             str(path)], capture_output=True, text=True, timeout=120)
    if result.returncode:
        raise ValueError('Unreadable source camera: ' + path.name)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or \
            streams[0].get('nb_read_frames') != str(FRAMES):
        raise ValueError('Source camera frame contract: ' + path.name)
    return sha(path)


def process(bundle, sources, *, synthetic=True):
    bundle, sources = Path(bundle), Path(sources)
    checked = check(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    raw_path = sources / 'native-actors.jsonl'
    map_path = sources / 'video_frames.jsonl'
    review_path = sources / 'review.json'
    requested = read_rows(bundle / 'requested-tracks.jsonl')
    actors, frames = read_rows(raw_path), read_rows(map_path)
    review = json.loads(review_path.read_text())
    if len(actors) != FRAMES or len(frames) != FRAMES or len(requested) != FRAMES:
        raise ValueError('600 source frames required')
    expected = 'synthetic_fixture' if synthetic else 'original_native_review'
    if (review.get('source_kind') != expected or
            review.get('case_id') != config['case_id'] or
            review.get('candidate_id') != 'primary' or
            review.get('native_actors_sha256') != sha(raw_path) or
            review.get('video_frames_sha256') != sha(map_path)):
        raise ValueError('Source review identity or hashes')
    videos = {name + '.mkv': media(sources / (name + '.mkv')) for name in CAMERAS}
    if review.get('media_sha256') != videos:
        raise ValueError('Source camera hashes changed')
    first_intersection = []
    right_turn = []
    straight_through = []
    previous = None
    actor_ids = set()
    for index, (actor, frame, request) in enumerate(zip(actors, frames, requested)):
        point = actor.get('ego_xy_m')
        if (actor.get('frame') != index or frame.get('video_frame') != index or
                actor.get('native_frame') != 1000 + index or
                frame.get('native_frame') != 1000 + index or
                actor.get('time_s') != request['time_s'] or
                frame.get('time_s') != request['time_s'] or
                actor.get('source_kind') != expected or
                actor.get('requested_x_m') != request['requested_x_m'] or
                actor.get('requested_y_m') != request['requested_y_m'] or
                actor.get('requested_heading_deg') != request['requested_heading_deg'] or
                not isinstance(point, list) or len(point) != 2 or
                not all(type(x) in (int, float) and math.isfinite(x) for x in point) or
                any(abs(point[j] - request[k]) > 1e-6 for j, k in
                    enumerate(('requested_x_m', 'requested_y_m'))) or
                actor.get('heading_deg') != request['requested_heading_deg'] or
                actor.get('stand_designation_verified') is not False or
                actor.get('posted_notice_verified') is not False or
                actor.get('taxi_license_verified') is not False or
                actor.get('first_intersection_native_verified') is not False or
                actor.get('legal_verdict') is not None):
            raise ValueError('Actor, request, frame or unverified authority changed')
        if type(actor.get('actor_id')) is not int or actor.get('blueprint') != 'vehicle.tesla.model3':
            raise ValueError('Actor identity changed')
        actor_ids.add(actor['actor_id'])
        if previous is not None and math.dist(previous, point) > 5.1 / RATE:
            raise ValueError('Actor motion discontinuity')
        previous = point
        first_intersection.append(point[0] >= 80)
        right_turn.append(point[0] == 80 and point[1] < 0 and actor['heading_deg'] == -90)
        straight_through.append(point[0] > 80 and point[1] == 0 and actor['heading_deg'] == 0)
    if len(actor_ids) != 1:
        raise ValueError('Actor continuity changed')
    first = lambda values: next((i for i, value in enumerate(values) if value), None)
    measured = 'right' if first(right_turn) is not None else 'straight' if first(straight_through) is not None else 'none'
    return {'format': 'c110875-source-only-taxi-measurement-v1',
            'case_id': checked['case_id'], 'candidate_id': 'primary',
            'source_kind': 'synthetic_cpu' if synthetic else 'original_native_unreviewed',
            'frames': FRAMES, 'rate_hz': RATE,
            'first_intersection_station_m': 80,
            'first_intersection_approach_frame': first(first_intersection),
            'first_right_turn_frame': first(right_turn),
            'first_straight_through_frame': first(straight_through),
            'measured_first_turn': measured,
            'requested_first_turn': config['requested_first_turn'],
            'turn_request_matched': measured == config['requested_first_turn'],
            'camera_sha256': videos,
            'stand_designation_established': False,
            'posted_notice_established': False,
            'taxi_license_established': False,
            'first_intersection_native_established': False,
            'legal_verdict': None, 'delivery_ready': False}

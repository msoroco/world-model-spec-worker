"""Source-bound CPU diagnostic for roundabout lane and following traffic."""

import hashlib
import json
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder):
    folder = Path(folder)
    source = json.loads((folder / 'sources.json').read_text())
    if source.get('kind') != 'synthetic_cpu_roundabout_diagnostic':
        raise ValueError('Synthetic source provenance differs')
    for name in ('geometry.json', 'actors.jsonl'):
        if digest(folder / name) != source['sha256'][name]:
            raise ValueError('Source hash differs: ' + name)
    geometry = json.loads((folder / 'geometry.json').read_text())
    if geometry['outer_right_lane_radius_m'] != [13.0, 16.0] or geometry['inner_left_lane_radius_m'] != [10.0, 13.0]:
        raise ValueError('Roundabout lane geometry differs')
    rows = [json.loads(line) for line in (folder / 'actors.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Expected 600 Native frames')
    counts = {'outer_right': 0, 'inner_left': 0, 'other': 0, 'follower_behind': 0, 'ego_slower_than_follower': 0}
    min_following_arc_m = None
    for index, row in enumerate(rows):
        if row['frame'] != 1000 + index or abs(row['time_s'] - index / 20) > 1e-8:
            raise ValueError('Native frame/time join differs')
        if set(row['actors']) != {'ego', 'follower'}:
            raise ValueError('Ego/follower source missing')
        ego = row['actors']['ego']
        follower = row['actors']['follower']
        if ego['speed_mps'] < 0 or follower['speed_mps'] < 0:
            raise ValueError('Negative source speed')
        er = math.hypot(ego['x_m'], ego['y_m'])
        fr = math.hypot(follower['x_m'], follower['y_m'])
        lane = 'outer_right' if 13.0 <= er < 16.0 else 'inner_left' if 10.0 <= er < 13.0 else 'other'
        counts[lane] += 1
        theta_ego = math.atan2(ego['y_m'], ego['x_m'])
        theta_follow = math.atan2(follower['y_m'], follower['x_m'])
        trailing_angle = (theta_ego - theta_follow) % (2 * math.pi)
        if abs(fr - er) < 0.01 and 0 < trailing_angle < math.pi:
            counts['follower_behind'] += 1
            arc = er * trailing_angle
            min_following_arc_m = arc if min_following_arc_m is None else min(arc, min_following_arc_m)
        if ego['speed_mps'] < follower['speed_mps']:
            counts['ego_slower_than_follower'] += 1
    return {
        'source_kind': source['kind'], 'source_sha256': source['sha256'],
        'frames': len(rows), 'rate_hz': 20, 'counts': counts,
        'min_following_arc_m': round(min_following_arc_m, 6) if min_following_arc_m is not None else None,
        'impeding_judgment': 'unresolved', 'passing_exception_necessity': 'unresolved',
        'physical_native_verified': False, 'legal_verdict_claimed': False,
    }

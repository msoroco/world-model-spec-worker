"""Source-bound draft measurement of center-lane travel after a left turn.

The event interval uses original Native frame, road/lane, pose and body samples.
An authored lane rectangle is only a CPU diagnostic, not Native lane-design proof.
"""
import hashlib
import json
import math
from pathlib import Path

THRESHOLD_M = 50 * 0.3048


def _point(value, label):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('Missing Native point: ' + label)
    result = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in result):
        raise ValueError('Nonfinite Native point: ' + label)
    return result


def _box(value, label):
    if not isinstance(value, list) or len(value) != 4:
        raise ValueError('Missing Native bounds: ' + label)
    result = tuple(float(x) for x in value)
    if not all(math.isfinite(x) for x in result) or result[0] >= result[2] or result[1] >= result[3]:
        raise ValueError('Invalid Native bounds: ' + label)
    return result


def _inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def _body_overlaps_box(body, box):
    # The constructed highway strips and complete observed body are convex.
    if any(_inside(p, box) for p in body):
        return True
    for i in range(4):
        a, b = body[i], body[(i + 1) % 4]
        dx, dy = b[0] - a[0], b[1] - a[1]
        lo, hi = 0.0, 1.0
        for p, q in ((-dx, a[0]-box[0]), (dx, box[2]-a[0]),
                     (-dy, a[1]-box[1]), (dy, box[3]-a[1])):
            if abs(p) < 1e-12:
                if q < 0:
                    break
            else:
                t = q / p
                if p < 0:
                    lo = max(lo, t)
                else:
                    hi = min(hi, t)
                if lo > hi:
                    break
        else:
            return True
    return False


def measure(samples_path, geometry_path):
    samples_path, geometry_path = Path(samples_path), Path(geometry_path)
    if not samples_path.is_file() or not geometry_path.is_file():
        raise ValueError('Required original Native source missing')
    g = json.loads(geometry_path.read_text())
    center_box = _box(g.get('center_turn_lane_native_xy_bounds_m'), 'center lane')
    through_box = _box(g.get('through_lane_native_xy_bounds_m'), 'through lane')
    center_lane, through_lane = g.get('center_turn_lane_native_id'), g.get('through_lane_native_id')
    connector_road, highway_road = g.get('left_turn_connector_road_id'), g.get('highway_road_id')
    if not all(isinstance(v, int) for v in (center_lane, through_lane, connector_road, highway_road)):
        raise ValueError('Native road or lane identity missing')
    if center_lane == through_lane or connector_road == highway_road:
        raise ValueError('Native road or lane identities overlap')
    forward = _point(g.get('highway_forward_native_xy'), 'highway forward')
    if abs(math.hypot(*forward)-1) > .01:
        raise ValueError('Highway forward is not a unit vector')
    rows = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
    if len(rows) < 5:
        raise ValueError('Too few Native samples')
    cumulative, centers, bodies, headings = [], [], [], []
    last_frame, last_time = -1, -math.inf
    for row in rows:
        frame, time = row.get('native_frame'), float(row['time_s'])
        if not isinstance(frame, int) or frame <= last_frame or not math.isfinite(time) or time <= last_time:
            raise ValueError('Native frame/time order invalid')
        last_frame, last_time = frame, time
        center = _point(row.get('native_center_xy_m'), 'body center')
        body = [_point(p, 'body corner') for p in row.get('native_body_xy_m', [])]
        if len(body) != 4:
            raise ValueError('Original four-corner Native body missing')
        heading = _point(row.get('native_forward_xy'), 'heading')
        if abs(math.hypot(*heading)-1) > .01:
            raise ValueError('Native heading is not a unit vector')
        cumulative.append((cumulative[-1] if cumulative else 0) +
                          (math.dist(centers[-1], center) if centers else 0))
        centers.append(center); bodies.append(body); headings.append(heading)

    completion = None
    for i in range(1, len(rows)):
        prev, row = rows[i-1], rows[i]
        cross = headings[i-1][0]*headings[i][1] - headings[i-1][1]*headings[i][0]
        dot = headings[i][0]*forward[0] + headings[i][1]*forward[1]
        if (prev.get('native_road_id') == connector_road and row.get('native_road_id') == highway_road
            and row.get('native_lane_id') == center_lane
            and all(_inside(p, center_box) for p in bodies[i])
            and dot >= math.cos(math.radians(5)) and cross <= -math.sin(math.radians(30))):
            completion = i
            break
    if completion is None:
        raise ValueError('Observed left turn into center lane absent')
    onset = next((i for i in range(completion+1, len(rows))
                  if _body_overlaps_box(bodies[i], through_box)), None)
    if onset is None:
        raise ValueError('Observed merge onset absent')
    if not all(rows[i].get('native_road_id') == highway_road and
               rows[i].get('native_lane_id') == center_lane and
               _body_overlaps_box(bodies[i], center_box)
               for i in range(completion, onset)):
        raise ValueError('Continuous center-lane travel absent')
    completed_merge = next((i for i in range(onset, len(rows))
                            if rows[i].get('native_lane_id') == through_lane and
                            all(_inside(p, through_box) for p in bodies[i])), None)
    if completed_merge is None:
        raise ValueError('Full-body merge into traffic lane absent')
    lower = max(0, cumulative[onset-1] - cumulative[completion])
    upper = cumulative[onset] - cumulative[completion-1]
    relation = ('within_50_feet' if upper < THRESHOLD_M else
                'exceeds_50_feet' if lower > THRESHOLD_M else 'unresolved_at_50_feet')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (samples_path, geometry_path)}
    return {'format': 'center-lane-after-left-turn-to-merge-v1',
            'threshold_m': THRESHOLD_M,
            'threshold_source': 'NRS 484B.223(3)(c): 50 feet',
            'turn_completion_frame_bracket': [rows[completion-1]['native_frame'], rows[completion]['native_frame']],
            'merge_onset_frame_bracket': [rows[onset-1]['native_frame'], rows[onset]['native_frame']],
            'full_merge_native_frame': rows[completed_merge]['native_frame'],
            'distance_interval_m': [lower, upper],
            'sampled_distance_m': cumulative[onset]-cumulative[completion],
            'threshold_relation': relation,
            'native_center_lane_design_verified': g.get('native_center_lane_design_verified') is True,
            'source_hashes': hashes,
            'limitations': ['Sample brackets do not locate continuous turn completion or merge onset exactly',
                            'Native center-lane designation and legal outcome require independent evidence']}

"""Original-tick geometry for simultaneous opposing left turns.

The output is a measured trajectory description, not a legal classification.
Only original Native body/heading samples and map/device inventory may be input.
"""

import json
import hashlib
from math import hypot, isfinite
from pathlib import Path


def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2 or not all(
            isinstance(x, (int, float)) and isfinite(x) for x in value):
        raise ValueError(f'{name} needs a finite XY pair')
    return (float(value[0]), float(value[1]))


def _rows(path, name):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f'missing original {name} samples')
    frames = [r.get('frame') for r in rows]
    if any(type(f) is not int for f in frames) or frames != sorted(set(frames)):
        raise ValueError(f'nonmonotonic original {name} frames')
    return {r['frame']: r for r in rows}


def _corners(value):
    if not isinstance(value, list) or len(value) < 4:
        raise ValueError('original ground-body corners are missing')
    return [_point(corner, 'ground-body corner') for corner in value]


def _segment_distance(point, a, b):
    vx, vy = b[0]-a[0], b[1]-a[1]
    squared = vx*vx+vy*vy
    if squared < 1e-12:
        return hypot(point[0]-a[0], point[1]-a[1])
    t = max(0., min(1., ((point[0]-a[0])*vx+(point[1]-a[1])*vy)/squared))
    return hypot(point[0]-(a[0]+t*vx), point[1]-(a[1]+t*vy))


def _cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])


def _intersect(a, b, c, d):
    if (max(min(a[0], b[0]), min(c[0], d[0])) >
            min(max(a[0], b[0]), max(c[0], d[0])) or
            max(min(a[1], b[1]), min(c[1], d[1])) >
            min(max(a[1], b[1]), max(c[1], d[1]))):
        return False
    return _cross(a, b, c)*_cross(a, b, d) <= 0 and _cross(c, d, a)*_cross(c, d, b) <= 0


def _inside(point, polygon):
    inside = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        if (a[1] > point[1]) != (b[1] > point[1]):
            crossing_x = a[0] + (point[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if point[0] < crossing_x:
                inside = not inside
    return inside


def _body_clearance(a, b):
    edges_a = list(zip(a, a[1:]+a[:1]))
    edges_b = list(zip(b, b[1:]+b[:1]))
    if (any(_intersect(p, q, r, s) for p, q in edges_a for r, s in edges_b) or
            _inside(a[0], b) or _inside(b[0], a)):
        return 0.
    return min([_segment_distance(p, r, s) for p in a for r, s in edges_b] +
               [_segment_distance(p, r, s) for p in b for r, s in edges_a])


def measure(subject_path, opposing_path, topology_path, device_path):
    """Return per-tick relative geometry while both vehicles turn in the junction.

    Heading is the measured front direction, not an inferred route label. The
    nearest-center tick and signed projections preserve information needed for
    a later independent front/behind review without declaring a legal cutoff.
    """
    topology = json.loads(Path(topology_path).read_text())
    devices = json.loads(Path(device_path).read_text())
    if not topology.get('both_highways_two_directional'):
        raise ValueError('original map inventory does not establish two-directional highways')
    if not topology.get('same_intersection') or not topology.get('opposing_approaches'):
        raise ValueError('original map inventory does not establish opposing approaches')
    if 'governing_device' not in devices or devices['governing_device'] not in (
            'none', 'directs_alternate', 'unresolved'):
        raise ValueError('original governing-device inventory is missing')
    subject = _rows(subject_path, 'subject')
    opposing = _rows(opposing_path, 'opposing')
    if subject.keys() != opposing.keys():
        raise ValueError('subject and opposing original frame sets differ')
    observations = []
    previous_time = None
    for frame in subject:
        a, b = subject[frame], opposing[frame]
        ta, tb = a.get('time_s'), b.get('time_s')
        if not all(isinstance(v, (int, float)) and isfinite(v) for v in (ta, tb)):
            raise ValueError('missing original frame times')
        if abs(ta-tb) > 1e-6 or (previous_time is not None and ta <= previous_time):
            raise ValueError('original turn sources are not time joined')
        previous_time = ta
        if not (a.get('in_intersection') and b.get('in_intersection') and
                a.get('turning_left') and b.get('turning_left')):
            continue
        pa, pb = _point(a.get('center_xy'), 'subject center'), _point(b.get('center_xy'), 'opposing center')
        ha, hb = _point(a.get('heading_xy'), 'subject heading'), _point(b.get('heading_xy'), 'opposing heading')
        corners_a, corners_b = _corners(a.get('ground_corners_xy')), _corners(b.get('ground_corners_xy'))
        na, nb = hypot(*ha), hypot(*hb)
        if na < 1e-6 or nb < 1e-6:
            raise ValueError('zero measured heading')
        dx, dy = pb[0]-pa[0], pb[1]-pa[1]
        observations.append({
            'frame': frame, 'time_s': float(ta), 'center_distance_m': hypot(dx, dy),
            'ground_body_clearance_m': _body_clearance(corners_a, corners_b),
            'opposing_ahead_of_subject_m': (dx*ha[0]+dy*ha[1])/na,
            'subject_ahead_of_opposing_m': (-dx*hb[0]-dy*hb[1])/nb,
            'opposing_left_of_subject_m': (ha[0]*dy-ha[1]*dx)/na,
            'subject_left_of_opposing_m': (hb[1]*dx-hb[0]*dy)/nb,
        })
    if len(observations) < 2:
        raise ValueError('no sustained simultaneous original left-turn interval')
    closest = min(observations, key=lambda r: r['center_distance_m'])
    source_refs = [{'path': str(Path(path)),
                    'sha256': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                   for path in (subject_path, opposing_path, topology_path, device_path)]
    return {
        'format': 'opposing-left-turn-original-geometry-v1',
        'law_id': 'NRS-484B-400-2c', 'governing_device': devices['governing_device'],
        'simultaneous_frames': len(observations), 'first_frame': observations[0]['frame'],
        'last_frame': observations[-1]['frame'], 'closest': closest,
        'observations': observations, 'legal_front_of_each_other': 'unreviewed',
        'physical_completion': 'unreviewed',
        'source_refs': source_refs,
    }

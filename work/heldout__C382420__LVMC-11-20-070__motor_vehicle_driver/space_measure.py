"""Original-frame measurements for the crosswalk/intersection entry question.

The returned values are geometric observations.  They do not decide whether
space is legally sufficient or whether passage was legally obstructed.
"""
from __future__ import annotations

from math import hypot
from shapely.geometry import Polygon


def polygon(points, label):
    shape = Polygon(points)
    if not shape.is_valid or shape.is_empty or shape.area <= 0:
        raise ValueError(f"Invalid {label} polygon")
    return shape


def _axis(scene):
    start, end = scene['other_side_origin'], scene['receiving_path_end']
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = hypot(dx, dy)
    if length <= 0:
        raise ValueError('Receiving path has no length')
    return start, (dx / length, dy / length), length


def _project(point, origin, direction):
    return (point[0] - origin[0]) * direction[0] + (point[1] - origin[1]) * direction[1]


def _available_length(scene, row):
    origin, direction, limit = _axis(scene)
    corridor = polygon(scene['receiving_corridor'], 'receiving corridor')
    obstacle_intervals = []
    for obstacle in row['downstream_occupants']:
        body = polygon(obstacle['footprint'], 'downstream occupant')
        if not body.intersects(corridor):
            continue
        projections = [_project(point, origin, direction) for point in body.exterior.coords]
        low, high = min(projections), max(projections)
        if high >= 0 and low <= limit:
            obstacle_intervals.append((max(0.0, low), min(limit, high), obstacle['id']))
    obstacle_intervals.sort()
    first = obstacle_intervals[0] if obstacle_intervals else None
    return (first[0] if first else limit), first, obstacle_intervals


def analyze(scene, frames):
    """Join 20 Hz original bodies, space, signal and participant route sources."""
    if scene.get('region_kind') not in ('marked_crosswalk', 'intersection'):
        raise ValueError('Entry region is neither marked crosswalk nor intersection')
    region = polygon(scene['entry_region'], 'entry region')
    polygon(scene['receiving_corridor'], 'receiving corridor')
    vehicle_length = scene['vehicle_length_m']
    if not isinstance(vehicle_length, (float, int)) or vehicle_length <= 0:
        raise ValueError('Measured vehicle length missing')
    if not frames:
        raise ValueError('No original frames')
    previous_inside = False
    entry = None
    occupancies = []
    seen_frames = set()
    first_time = frames[0]['time_s']
    for index, row in enumerate(frames):
        frame = row['frame']
        if type(frame) is not int or frame in seen_frames or frame != index:
            raise ValueError('Original frame identities are not continuous')
        seen_frames.add(frame)
        if abs((row['time_s'] - first_time) - frame / 20.0) > 1e-6:
            raise ValueError('Original frame/time join changed')
        if row.get('signal_state') is None:
            raise ValueError('Signal readback missing')
        body = polygon(row['ego_footprint'], 'ego body')
        inside = body.intersects(region)
        if inside and not previous_inside and entry is None:
            free, first, intervals = _available_length(scene, row)
            entry = {'frame': frame, 'time_s': row['time_s'],
                     'region_kind': scene['region_kind'],
                     'signal_state': row['signal_state'],
                     'measured_vehicle_length_m': float(vehicle_length),
                     'downstream_available_length_m': free,
                     'first_downstream_occupant': first[2] if first else None,
                     'downstream_occupant_intervals_m': intervals,
                     'body_intersects_entry_region': True}
        if entry is not None:
            for participant in row['passage_participants']:
                path = polygon(participant['passage_polygon'], 'participant passage')
                occupancy = body.intersection(path).area
                occupancies.append({'frame': frame, 'participant_id': participant['id'],
                                    'participant_kind': participant['kind'],
                                    'ego_overlap_area_m2': occupancy,
                                    'passage_polygon_observed': True})
        previous_inside = inside
    if entry is None:
        raise ValueError('Ego never entered the marked source region')
    return {'entry': entry, 'passage_occupancies': occupancies,
            'any_passage_overlap': any(x['ego_overlap_area_m2'] > 0 for x in occupancies),
            'legal_sufficiency_decided': False, 'legal_obstruction_decided': False,
            'source_kind': 'original-frame geometry'}

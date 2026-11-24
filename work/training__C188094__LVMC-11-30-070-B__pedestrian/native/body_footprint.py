"""Conservative body-footprint containment from original Native geometry inputs."""
import json
import math
from pathlib import Path


def finite(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Invalid original ' + label)
    return float(value)


def corners(row, extent):
    x = finite(row.get('pedestrian_x_m'), 'pedestrian x')
    y = finite(row.get('pedestrian_y_m'), 'pedestrian y')
    yaw = math.radians(finite(row.get('pedestrian_yaw_deg'), 'pedestrian yaw'))
    ex = finite(extent.get('x_m'), 'body x extent')
    ey = finite(extent.get('y_m'), 'body y extent')
    if ex <= 0 or ey <= 0:
        raise ValueError('Missing positive original body extents')
    c, s = math.cos(yaw), math.sin(yaw)
    return [(x + dx*c - dy*s, y + dx*s + dy*c)
            for dx in (-ex, ex) for dy in (-ey, ey)]


def contains(bounds, points):
    return all(bounds['min_x'] <= x <= bounds['max_x'] and
               bounds['min_y'] <= y <= bounds['max_y'] for x, y in points)


def overlaps_rectangle(points, bounds):
    """Closed convex body polygon overlaps an axis-aligned roadway rectangle."""
    unique = sorted(set(points))
    if len(unique) < 3:
        raise ValueError('Original body footprint polygon incomplete')
    cx = sum(p[0] for p in unique) / len(unique)
    cy = sum(p[1] for p in unique) / len(unique)
    polygon = sorted(unique, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    road = [(bounds[x], bounds[y]) for x in ('min_x', 'max_x')
            for y in ('min_y', 'max_y')]
    axes = [(1, 0), (0, 1)]
    axes.extend((polygon[(i + 1) % len(polygon)][1] - p[1],
                 p[0] - polygon[(i + 1) % len(polygon)][0])
                for i, p in enumerate(polygon))
    for ax, ay in axes:
        body_projection = [ax*x + ay*y for x, y in polygon]
        road_projection = [ax*x + ay*y for x, y in road]
        if max(body_projection) < min(road_projection) or max(road_projection) < min(body_projection):
            return False
    return True


def measure(rows, context, geometry_source):
    if not isinstance(geometry_source, dict) or geometry_source.get('source_kind') != 'native_walker_bounding_box':
        raise ValueError('Original Native body geometry source missing')
    if geometry_source.get('pedestrian_id') != rows[0].get('pedestrian_id'):
        raise ValueError('Body geometry pedestrian identity mismatch')
    if len(rows) != 600:
        raise ValueError('Original body path incomplete')
    roadway = context['roadway_bounds_m']
    crosswalks = [item['bounds_m'] for item in context['crosswalks']]
    outside = []
    center_outside = []
    for index, row in enumerate(rows):
        if row.get('video_frame') != index or row.get('pedestrian_id') != geometry_source['pedestrian_id']:
            raise ValueError('Original body path identity mismatch')
        center = (finite(row.get('pedestrian_x_m'), 'pedestrian x'),
                  finite(row.get('pedestrian_y_m'), 'pedestrian y'))
        center_in_roadway = contains(roadway, [center])
        footprint = corners(row, geometry_source['extent_m'])
        if not overlaps_rectangle(footprint, roadway):
            continue
        if center_in_roadway and not any(contains(crosswalk, [center]) for crosswalk in crosswalks):
            center_outside.append(index)
        if not any(contains(crosswalk, footprint) for crosswalk in crosswalks):
            outside.append(index)
    return {'format': 'c188094-original-body-footprint-containment',
            'roadway_point_frames_outside_crosswalk': len(center_outside),
            'roadway_body_frames_not_wholly_inside_one_crosswalk': len(outside),
            'first_body_frame_not_wholly_inside_one_crosswalk': outside[0] if outside else None,
            'body_wholly_inside_one_crosswalk_at_every_roadway_sample': not outside,
            'sampling_rate_hz': 20, 'legal_verdict': 'unassessed',
            'limitations': ['Requires original Native walker bounding box and yaw at each frame',
                            'A crossing between sampled frames remains unobserved',
                            'Business-district and complete crossing inventory require separate source audit']}


def measure_evidence_body(poses, evidence, context):
    """Measure original per-frame evidence vertices joined to pedestrian poses."""
    if len(poses) != 600 or len(evidence) != 600:
        raise ValueError('Original Native pose/evidence source incomplete')
    roadway = context['roadway_bounds_m']
    crosswalks = [item['bounds_m'] for item in context['crosswalks']]
    outside, center_outside = [], []
    for index, (pose, frame) in enumerate(zip(poses, evidence)):
        if pose.get('video_frame') != index or pose.get('native_frame') != frame.get('original_frame'):
            raise ValueError('Original body/frame join differs')
        if pose.get('pedestrian_id') != frame.get('actor_id'):
            raise ValueError('Original body actor identity differs')
        center = (finite(pose.get('pedestrian_x_m'), 'pedestrian x'),
                  finite(pose.get('pedestrian_y_m'), 'pedestrian y'))
        vertices = frame.get('ego', {}).get('body_vertices_m')
        if not isinstance(vertices, list) or len(vertices) != 8 or any(not isinstance(v, list) or len(v) != 3 for v in vertices):
            raise ValueError('Original Native pedestrian body vertices missing')
        footprint = [(finite(v[0], 'body vertex x'), finite(v[1], 'body vertex y')) for v in vertices]
        center_in_roadway = contains(roadway, [center])
        if not overlaps_rectangle(footprint, roadway):
            continue
        if center_in_roadway and not any(contains(bounds, [center]) for bounds in crosswalks):
            center_outside.append(index)
        if not any(contains(bounds, footprint) for bounds in crosswalks):
            outside.append(index)
    return {'format': 'c188094-original-evidence-body-footprint-containment',
            'roadway_point_frames_outside_crosswalk': len(center_outside),
            'roadway_body_frames_not_wholly_inside_one_crosswalk': len(outside),
            'first_body_frame_not_wholly_inside_one_crosswalk': outside[0] if outside else None,
            'body_wholly_inside_one_crosswalk_at_every_roadway_sample': not outside,
            'sampling_rate_hz': 20, 'legal_verdict': 'unassessed',
            'limitations': ['Original Native bounding vertices require independent physical review',
                            'A crossing between sampled frames remains unobserved',
                            'Business-district and complete crossing inventory require separate source audit']}


def proof():
    context = {'roadway_bounds_m': {'min_x': -20, 'max_x': 20, 'min_y': -4, 'max_y': 4},
               'crosswalks': [{'bounds_m': {'min_x': -1, 'max_x': 1, 'min_y': -4, 'max_y': 4}}]}
    source = {'source_kind': 'native_walker_bounding_box', 'pedestrian_id': 7,
              'extent_m': {'x_m': 0.3, 'y_m': 0.25}}
    rows = [{'video_frame': i, 'pedestrian_id': 7, 'pedestrian_x_m': 0.5,
             'pedestrian_y_m': 0, 'pedestrian_yaw_deg': 0} for i in range(600)]
    inside = measure(rows, context, source)
    if inside['roadway_body_frames_not_wholly_inside_one_crosswalk'] != 0:
        raise AssertionError('wholly contained source body failed')
    rows[160]['pedestrian_x_m'] = 0.9
    escaped = measure(rows, context, source)
    if escaped['roadway_point_frames_outside_crosswalk'] != 0 or escaped['roadway_body_frames_not_wholly_inside_one_crosswalk'] != 1:
        raise AssertionError('point/body distinction failed')
    source['pedestrian_id'] = 8
    try:
        measure(rows, context, source)
    except ValueError as error:
        if 'identity' not in str(error):
            raise
    else:
        raise AssertionError('mismatched source identity accepted')
    source['pedestrian_id'] = 7
    edge = [dict(row, pedestrian_x_m=0.5, pedestrian_y_m=-4.15) for row in rows]
    overlap = measure(edge, context, source)
    if overlap['roadway_point_frames_outside_crosswalk'] != 0 or overlap['roadway_body_frames_not_wholly_inside_one_crosswalk'] != 600:
        raise AssertionError('body crossing roadway with center outside was skipped')
    return {'format': 'c188094-body-footprint-cpu-proof', 'passed': True,
            'positive_body_outside_frames': 0,
            'point_inside_body_outside_frames': 1,
            'center_outside_body_overlaps_roadway_frames': 600,
            'mismatched_identity_rejected': True,
            'original_native_geometry_supplied': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    output = Path(__file__).with_name('body-footprint-proof.json')
    output.write_text(json.dumps(proof(), indent=2) + '\n')
    print(output.read_text())

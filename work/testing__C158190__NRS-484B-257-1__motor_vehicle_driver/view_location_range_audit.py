"""Audit original Native sight histories for the unselected view-location axis.

This checks source geometry and continuity. It does not infer human perception or
legal adequacy, and a synthetic compatibility fixture cannot satisfy it.
"""
import json
import math
from pathlib import Path


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _point(value):
    return isinstance(value, list) and len(value) == 3 and all(_number(x) for x in value)


def audit(rows, context, *, min_frames=600, max_frame_gap=1):
    prop = context.get('view_occluder', {})
    if prop.get('source_kind') == 'synthetic_diagnostic':
        raise ValueError('Original Native road context required')
    if prop.get('blueprint') != 'static.prop.streetbarrier' or type(prop.get('actor_id')) is not int:
        raise ValueError('Original obstruction identity missing')
    center = prop.get('native_location_m')
    bounds = prop.get('body_bounds_m')
    if not _point(center) or not isinstance(bounds, dict) or any(
            axis not in bounds or not isinstance(bounds[axis], list)
            or len(bounds[axis]) != 2 or not all(_number(v) for v in bounds[axis])
            or bounds[axis][0] > bounds[axis][1] for axis in ('x', 'y', 'z')):
        raise ValueError('Original obstruction body envelope missing')
    if len(rows) < min_frames:
        raise ValueError('Original sight history is too short')
    frames, distances, prop_hits, clear = [], [], [], []
    for row in rows:
        frame = row.get('frame')
        distance = row.get('ego_distance_to_junction_m')
        observer, target = row.get('observer_m'), row.get('target_m')
        if type(frame) is not int or not _number(distance) or not _point(observer) or not _point(target):
            raise ValueError('Original sight frame or geometry missing')
        if row.get('method') != 'native_collision_ray_to_authored_through_lane_point':
            raise ValueError('Original Native collision ray required')
        if target != [1.8, 20.0, 1.5] or row.get('target_road_id') != 158194 or row.get('target_lane_id') != -1:
            raise ValueError('Through-lane target changed')
        blockers = row.get('blockers')
        if not isinstance(blockers, list) or row.get('clear') is not (len(blockers) == 0):
            raise ValueError('Original ray blocker state inconsistent')
        if frames and (frame <= frames[-1] or frame - frames[-1] > max_frame_gap):
            raise ValueError('Original sight frames are not contiguous')
        if distances and distance > distances[-1] + .05:
            raise ValueError('Approach distance reversed')
        hits = []
        for hit in blockers:
            location = hit.get('location_m') if isinstance(hit, dict) else None
            if not _point(location):
                raise ValueError('Original blocker location missing')
            segment = [target[j] - observer[j] for j in range(3)]
            length2 = sum(v*v for v in segment)
            if length2 <= 0:
                raise ValueError('Original sight ray has zero length')
            fraction = sum((location[j] - observer[j]) * segment[j] for j in range(3)) / length2
            miss2 = sum((location[j] - observer[j] - fraction*segment[j])**2 for j in range(3))
            if fraction < 0 or fraction > 1 or miss2 > .25**2:
                raise ValueError('Original blocker lies off sight ray')
            if all(bounds[axis][0] <= location[index] <= bounds[axis][1]
                   for index, axis in enumerate(('x', 'y', 'z'))):
                hits.append(location)
        frames.append(frame)
        distances.append(distance)
        prop_hits.append(bool(hits))
        clear.append(row['clear'])
    if max(distances) < 50 or min(distances) > 1:
        raise ValueError('Original sight history does not span authored approach')
    if not any(prop_hits) or not any(clear):
        raise ValueError('Original obstruction lacks a clear/blocked contrast')
    transitions = [frames[i] for i in range(1, len(rows)) if prop_hits[i] != prop_hits[i-1]]
    if not transitions:
        raise ValueError('Original obstruction has no observed transition')
    return {'source_kind': 'original_native', 'frames': len(rows),
            'first_frame': frames[0], 'last_frame': frames[-1],
            'distance_range_m': [min(distances), max(distances)],
            'obstruction_actor_id': prop['actor_id'],
            'observed_transition_frames': transitions,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def audit_files(ray_path, context_path):
    rays = [json.loads(line) for line in Path(ray_path).read_text().splitlines()]
    return audit(rays, json.loads(Path(context_path).read_text()))


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('rays')
    parser.add_argument('road_context')
    args = parser.parse_args()
    print(json.dumps(audit_files(args.rays, args.road_context), indent=2))

"""Measure sampled body overlap with a divided-highway opening and barrier.

This reports geometry only. It does not establish public-authority designation,
physical Native driving, right-of-way, or a legal result.
"""
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clip(points, axis, boundary, keep_greater):
    def inside(point):
        return point[axis] >= boundary if keep_greater else point[axis] <= boundary
    result = []
    for start, end in zip(points, points[1:] + points[:1]):
        a, b = inside(start), inside(end)
        if a != b:
            denominator = end[axis] - start[axis]
            if abs(denominator) < 1e-12:
                raise ValueError('Degenerate polygon edge')
            ratio = (boundary - start[axis]) / denominator
            result.append([start[k] + ratio * (end[k] - start[k]) for k in (0, 1)])
        if b:
            result.append(end)
    return result


def overlap_area(points, bounds):
    clipped = [[float(x), float(y)] for x, y in points]
    if len(clipped) != 4 or not all(math.isfinite(value) for point in clipped for value in point):
        raise ValueError('Four finite source body vertices required')
    xmin, ymin, xmax, ymax = bounds
    for axis, boundary, greater in ((0,xmin,True),(0,xmax,False),
                                     (1,ymin,True),(1,ymax,False)):
        if not clipped:
            return 0.0
        clipped = clip(clipped, axis, boundary, greater)
    area = abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in
                   zip(clipped, clipped[1:]+clipped[:1])))/2
    return area


def evaluate(folder):
    folder = Path(folder)
    manifest = json.loads((folder/'sources.json').read_text())
    if manifest.get('source_kind') != 'synthetic_cpu_geometry_diagnostic' or \
            manifest.get('accepted') is not False:
        raise ValueError('Synthetic source cannot be relabeled original Native')
    for name, digest in manifest['sha256'].items():
        if sha(folder/name) != digest:
            raise ValueError('Source hash differs: '+name)
    geometry = json.loads((folder/'geometry.json').read_text())
    if geometry['median_bounds_m'] != [-20,-2,20,2] or \
            geometry['opening_bounds_m'] != [-3,-2,3,2] or \
            geometry['barrier_bounds_m'] != [[-20,-2,-3,2],[3,-2,20,2]]:
        raise ValueError('Authored median geometry changed')
    rows = [json.loads(line) for line in (folder/'body.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('600 sampled body rows required')
    median_frames = []
    opening_frames = []
    barrier_frames = []
    maximum = {'median_m2':0.0,'opening_m2':0.0,'barrier_m2':0.0}
    for index,row in enumerate(rows):
        if row['native_frame'] != 1000+index or row['video_frame'] != index or \
                abs(row['time_s']-index/20) > 1e-6:
            raise ValueError('Native 20 Hz frame/time join differs')
        body = row['native_body_xy_m']
        median = overlap_area(body,geometry['median_bounds_m'])
        opening = overlap_area(body,geometry['opening_bounds_m'])
        barrier = sum(overlap_area(body,bounds) for bounds in geometry['barrier_bounds_m'])
        if abs(median-opening-barrier) > 1e-6:
            raise ValueError('Median opening/barrier area partition differs')
        if median > 1e-6:
            median_frames.append(row['native_frame'])
            if row['speed_mps'] <= 0:
                raise ValueError('Stopped body cannot establish driven crossing')
        if opening > 1e-6:
            opening_frames.append(row['native_frame'])
        if barrier > 1e-6:
            barrier_frames.append(row['native_frame'])
        for key,value in (('median_m2',median),('opening_m2',opening),('barrier_m2',barrier)):
            maximum[key] = max(maximum[key],value)
    if not median_frames:
        raise ValueError('No sampled median crossing')
    return {'case_suffix':manifest['case_suffix'],'source_kind':manifest['source_kind'],
            'source_sha256':manifest['sha256'],'frame_count':len(rows),'rate_hz':20,
            'median_occupied_frames':len(median_frames),
            'opening_occupied_frames':len(opening_frames),
            'barrier_occupied_frames':len(barrier_frames),
            'first_median_frame':median_frames[0],
            'last_median_frame':median_frames[-1],
            'max_overlap_m2':{key:round(value,6) for key,value in maximum.items()},
            'authority_verified':False,'physical_native_verified':False,
            'legal_verdict_claimed':False}

"""Portable result/geometry checks. Used by CPU fixtures and live finalization."""
import math
from pathlib import Path
from .common import read


def validate_result(directory, result):
    directory=Path(directory)
    for key in ('setup_confirmed','behavior_attempted','maneuver_completed'):
        if result.get(key) is not True:raise ValueError('Incomplete '+key)
    if result.get('physical_failure_flags'):raise ValueError('Physical/capture failures remain')
    videos=result.get('video_references')
    if not videos or any(not isinstance(v,str) for v in videos):raise ValueError('Encoded video file paths required')
    for name in videos:
        path=(directory/name).resolve()
        if directory.resolve() not in path.parents or not path.is_file():raise ValueError('Missing contained video')
    for key in ('trace_reference','video_frame_map_reference'):
        if not isinstance(result.get(key),str) or not (directory/result[key]).is_file():raise ValueError('Missing '+key)
    if not result.get('target_checks'):raise ValueError('Missing measured target checks')
    return True


def channel_samples(samples, expected_frames):
    if len(samples)!=expected_frames:raise ValueError('Incomplete channel history')
    for sample in samples:
        if sample.get('value') is None or sample.get('missing_capability'):raise ValueError('Unimplemented mandatory channel')
        if not isinstance(sample.get('time_s'),(int,float)) or not math.isfinite(sample['time_s']):raise ValueError('Invalid time')
    if any(a['time_s']>=b['time_s'] for a,b in zip(samples,samples[1:])):raise ValueError('Nonincreasing times')
    return True


def route_contained(vertices, polygon):
    """All supplied footprint vertices must lie in the authored reference polygon."""
    def inside(p):
        x,y=p;odd=False
        for a,b in zip(polygon,polygon[1:]+polygon[:1]):
            cross=(x-a[0])*(b[1]-a[1])-(y-a[1])*(b[0]-a[0])
            if abs(cross)<1e-9 and min(a[0],b[0])<=x<=max(a[0],b[0]) and min(a[1],b[1])<=y<=max(a[1],b[1]):return True
            if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:odd=not odd
        return odd
    if not polygon or not vertices or not all(inside(v) for v in vertices):raise ValueError('Footprint outside reference region')
    return True


def footprint_contained(footprint, surfaces):
    """Check an ordered 2-D footprint against the UNION of roadway polygons.

    Inputs share one declared coordinate frame. No buffering, invented hull,
    repaired polygons or vertex-only substitution is allowed here.
    """
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    body=Polygon(footprint);roads=[Polygon(p) for p in surfaces]
    if not body.is_valid or body.is_empty or body.area<=0 or not roads or any(not r.is_valid or r.is_empty for r in roads):
        raise ValueError('Invalid observed footprint or roadway polygon')
    if not unary_union(roads).covers(body):raise ValueError('Body crosses unsupported surface')
    return True

"""Examples of case-specific measurements from recorded geometry and rays.

These return measurements, not statutory verdicts. The original capture must
still establish the roadway designation, actor identity and camera visibility.
"""
import math


def centerline_offset(road_direction_xy, centerline_point_xy, body_vertices_xy):
    """Signed perpendicular distances of every body vertex from a directed centerline."""
    dx,dy=road_direction_xy
    norm=math.hypot(dx,dy)
    if norm<=0 or len(body_vertices_xy)<3:raise ValueError('Directed road and body vertices required')
    distances=[(dx*(y-centerline_point_xy[1])-dy*(x-centerline_point_xy[0]))/norm
               for x,y in body_vertices_xy]
    return {'signed_vertex_distances_m':distances,
            'minimum_m':min(distances),'maximum_m':max(distances),
            'road_direction_xy':list(road_direction_xy),
            'sampling_note':'same original frame; right-side interpretation depends on verified direction'}


def nearest_visible_point(samples):
    """Nearest observed approach point to the intersection with a clear ray."""
    if not samples:raise ValueError('Original viewpoint samples required')
    candidates=[]
    for item in samples:
        if not all(k in item for k in ('point_xy_m','distance_to_intersection_m','clear_ray','frame')):
            raise ValueError('Incomplete original viewpoint sample')
        if item['clear_ray'] is True:
            candidates.append(item)
    if not candidates:raise ValueError('No observed clear viewpoint')
    winner=min(candidates,key=lambda x:x['distance_to_intersection_m'])
    return {'point_xy_m':winner['point_xy_m'],
            'distance_to_intersection_m':winner['distance_to_intersection_m'],
            'frame':winner['frame'],'clear_sample_count':len(candidates),
            'sampling_note':'nearest among recorded samples; continuous nearest point and pixel visibility remain unverified'}

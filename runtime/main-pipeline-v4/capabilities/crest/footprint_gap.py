"""Full native-box footprint separation; no centre or component-gap substitution."""
import math
from shapely.geometry import MultiPoint

def footprint(vertices):
    if len(vertices)!=8 or any(len(v)!=3 or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) for x in v) for v in vertices):
        raise ValueError('Eight finite actual native world-space box vertices required')
    polygon=MultiPoint([(v[0],v[1]) for v in vertices]).convex_hull
    if polygon.geom_type!='Polygon' or polygon.area<=0 or not polygon.is_valid:
        raise ValueError('Degenerate native footprint')
    return polygon

def gap(first_vertices,second_vertices):
    """Minimum Euclidean distance of complete horizontal projected native boxes, m."""
    return footprint(first_vertices).distance(footprint(second_vertices))

def distance_constraint(first_vertices,second_vertices,minimum_m):
    if isinstance(minimum_m,bool) or not isinstance(minimum_m,(int,float)) or not math.isfinite(minimum_m) or minimum_m<0:
        raise ValueError('Finite nonnegative distance required')
    distance=gap(first_vertices,second_vertices)
    return {'nearest_footprint_gap_m':distance,'minimum_required_m':minimum_m,
            'every_footprint_point_satisfies_minimum':distance>=minimum_m,
            'convention':'minimum horizontal Euclidean polygon separation of all8actual native world box vertices for both actors',
            'native_precision':'uncalibrated; no exact equality claim'}

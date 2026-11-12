"""Source-bound building-frontage geometry for a 403(3) district candidate.

NRS 484B.010 defines a 600 ft road window and 300 ft qualifying building
frontage. Native building geometry alone does not identify business/industrial
use, establish district status, or resolve 403(3)'s turn-site alternatives.
"""
from math import hypot, isfinite

WINDOW_M = 182.88
FRONTAGE_M = 91.44
QUALIFYING_USES = {'business', 'industrial'}


def collect_native_buildings(world, carla, turn_xy, *, radius_m=250.0, boxes=None):
    """Retain nearby original CARLA building boxes with unknown legal use.

    CARLA's level bounding boxes are in world coordinates. Their list index
    identifies the source box within this map snapshot; no zoning is inferred.
    """
    x,y = (float(v) for v in turn_xy)
    if not all(isfinite(v) for v in (x,y,radius_m)) or radius_m <= WINDOW_M:
        raise ValueError('Invalid Native building collection radius')
    buildings = []
    if boxes is None:
        boxes = world.get_level_bbs(carla.CityObjectLabel.Buildings)
    for index, box in enumerate(boxes):
        center = box.location
        if hypot(float(center.x)-x,float(center.y)-y) > radius_m:
            continue
        vertices = box.get_world_vertices(carla.Transform())
        buildings.append({'source_id':'building-box-'+str(index),
                          'vertices_xy_m':[[float(p.x),float(p.y)] for p in vertices],
                          'use_class':None,'use_source_ref':None})
    return buildings


def _union_length(intervals, start, end):
    clipped = sorted((max(a,start), min(b,end)) for a,b in intervals if b > start and a < end)
    total = 0.0
    cursor = start
    for a,b in clipped:
        if b > max(a,cursor):
            total += b-max(a,cursor)
            cursor = b
    return total


def _max_frontage(intervals, window_m, other_intervals=()):
    if not intervals and not other_intervals:
        return {'window_start_m': -window_m/2, 'frontage_m': 0.0}
    starts = {-window_m, 0.0}
    for a,b in [*intervals,*other_intervals]:
        starts.update((max(-window_m,min(0.0,v)) for v in (a,b,a-window_m,b-window_m)))
    candidates = [(round(_union_length(intervals,s,s+window_m)+
                         _union_length(other_intervals,s,s+window_m),6), s)
                  for s in starts]
    total, start = max(candidates, key=lambda item: (item[0], -abs(item[1]+window_m/2)))
    return {'window_start_m': start, 'frontage_m': total}


def measure_frontage(buildings, turn_xy, forward_xy, *, window_m=WINDOW_M):
    """Project Native 2D building footprints onto a local road tangent.

    `use_class` may be known only with an independent source reference. All
    buildings contribute to built-frontage candidate geometry; only sourced
    business/industrial uses contribute to qualifying-use geometry.
    """
    x,y = (float(v) for v in turn_xy)
    fx,fy = (float(v) for v in forward_xy)
    norm = hypot(fx,fy)
    if (not all(isfinite(v) for v in (x,y,fx,fy,window_m)) or norm <= 0 or
            window_m <= 0):
        raise ValueError('Invalid 403(3) road frame')
    fx,fy = fx/norm, fy/norm
    records = []
    for building in buildings:
        source_id = building.get('source_id')
        vertices = building.get('vertices_xy_m')
        if not source_id or not isinstance(vertices,list) or len(vertices) < 3:
            raise ValueError('Original Native building footprint missing')
        points = [tuple(float(v) for v in point) for point in vertices]
        if any(len(point)!=2 or not all(isfinite(v) for v in point) for point in points):
            raise ValueError('Invalid original building vertex')
        along = [(px-x)*fx+(py-y)*fy for px,py in points]
        lateral = [-(px-x)*fy+(py-y)*fx for px,py in points]
        if min(lateral) <= 0 <= max(lateral):
            raise ValueError('Building footprint crosses local road center')
        use = building.get('use_class')
        citation = building.get('use_source_ref')
        if use is not None and (use not in QUALIFYING_USES | {'other'} or not citation):
            raise ValueError('Known building use needs permitted class and source')
        records.append({'source_id': str(source_id),
                        'vertices_xy_m': [list(point) for point in points],
                        'side': 'left' if min(lateral) > 0 else 'right',
                        'interval_m': [min(along),max(along)],
                        'use_class': use, 'use_source_ref': citation})
    report = {}
    for side in ('left','right'):
        all_intervals = [item['interval_m'] for item in records if item['side']==side]
        known_intervals = [item['interval_m'] for item in records
                           if item['side']==side and item['use_class'] in QUALIFYING_USES]
        report[side] = {'built': _max_frontage(all_intervals,window_m),
                        'sourced_qualifying_use': _max_frontage(known_intervals,window_m)}
    def side_intervals(side, qualifying=False):
        return [item['interval_m'] for item in records if item['side']==side and
                (not qualifying or item['use_class'] in QUALIFYING_USES)]
    return {'method':'Native building footprint projection onto local road tangent',
            'window_m': window_m, 'qualifying_frontage_m': FRONTAGE_M,
            'turn_xy_m':[x,y], 'forward_unit_xy':[fx,fy],
            'buildings':records, 'frontage_by_side':report,
            'combined_built':_max_frontage(side_intervals('left'),window_m,side_intervals('right')),
            'combined_sourced_qualifying_use':_max_frontage(side_intervals('left',True),window_m,
                                                            side_intervals('right',True)),
            'business_district_legal_judgment':None,
            'intersection_exception_status':None,
            'divided_highway_opening_exception_status':None,
            'limitations':['Local tangent projection approximates a curved road frontage.',
                           'Native building geometry alone does not establish business or industrial use.',
                           'An independent source must verify use and statutory exception context.']}


def select_403_3_candidate(world, carla, *, waypoint_spacing_m=2.0,
                           max_candidates=500):
    """Search a nonjunction centerline U-turn site with built frontage geometry.

    The 300 ft screen checks unclassified buildings only. It is a physical
    candidate, never a claim that their use satisfies NRS 484B.010.
    """
    from u_turn_construction import select_u_turn_scene
    if type(max_candidates) is not int or max_candidates <= 0:
        raise ValueError('Invalid 403(3) candidate search limit')
    mapping = world.get_map()
    boxes = world.get_level_bbs(carla.CityObjectLabel.Buildings)
    for index in range(max_candidates):
        try:
            scene = select_u_turn_scene(mapping,
                                        waypoint_spacing_m=waypoint_spacing_m,
                                        candidate_index=index)
        except ValueError as error:
            if 'No requested Native opposing-lane U-turn pair' in str(error):
                break
            raise
        waypoint = scene['approach']
        loc = waypoint.transform.location
        direction = waypoint.transform.get_forward_vector()
        turn_xy = (float(loc.x),float(loc.y))
        buildings = collect_native_buildings(world,carla,turn_xy,boxes=boxes)
        try:
            report = measure_frontage(buildings,turn_xy,
                                      (float(direction.x),float(direction.y)))
        except ValueError:
            continue
        if report['combined_built']['frontage_m'] >= FRONTAGE_M:
            report['candidate_index'] = index
            report['site_is_junction'] = bool(waypoint.is_junction)
            report['divided_highway_opening_exception_status'] = None
            return scene, report
    raise ValueError('No Native 403(3) built-frontage candidate with opposing lanes')

"""Native divided-highway geometry candidate for NRS 484B.227.

Lane separation and mapped guardrail/wall/fence boxes are physical sources.
They do not establish a legally divided highway, public-authority crossover,
intersection, or whether the U-turn actually crossed a barrier.
"""
from math import hypot, isfinite


def _xy(waypoint):
    location=waypoint.transform.location
    return float(location.x),float(location.y)


def _forward(waypoint):
    direction=waypoint.transform.get_forward_vector()
    x,y=float(direction.x),float(direction.y)
    length=hypot(x,y)
    if not isfinite(length) or length<=0:
        raise ValueError('Invalid Native divided-road heading')
    return x/length,y/length


def collect_native_dividers(world,carla):
    """Read source boxes once; CARLA labels are geometry, not legal status."""
    records=[]
    for label in ('GuardRail','Walls','Fences'):
        for index,box in enumerate(world.get_level_bbs(getattr(carla.CityObjectLabel,label))):
            vertices=box.get_world_vertices(carla.Transform())
            records.append({'source_id':label+'-'+str(index),
                            'label':label,
                            'vertices_xy_m':[[float(p.x),float(p.y)] for p in vertices]})
    return records


def measure_divider_candidate(scene,boxes,*,along_limit_m=25.0):
    approach,opposite=scene['approach'],scene['opposite']
    ax,ay=_xy(approach)
    bx,by=_xy(opposite)
    fx,fy=_forward(approach)
    separation=hypot(bx-ax,by-ay)
    widths=(float(approach.lane_width),float(opposite.lane_width))
    if (not all(isfinite(v) and v>0 for v in (*widths,separation,along_limit_m)) or
            int(approach.road_id)!=int(opposite.road_id) or
            int(approach.lane_id)==int(opposite.lane_id)):
        raise ValueError('Invalid Native opposing-lane divider source')
    gap=separation-sum(widths)/2
    middle=((ax+bx)/2,(ay+by)/2)
    matched=[]
    for box in boxes:
        vertices=box.get('vertices_xy_m')
        if not box.get('source_id') or box.get('label') not in ('GuardRail','Walls','Fences') or not isinstance(vertices,list) or len(vertices)<3:
            raise ValueError('Native divider box source missing')
        points=[tuple(float(v) for v in p) for p in vertices]
        if any(len(p)!=2 or not all(isfinite(v) for v in p) for p in points):
            raise ValueError('Invalid Native divider box vertex')
        along=[(x-middle[0])*fx+(y-middle[1])*fy for x,y in points]
        across=[-(x-ax)*fy+(y-ay)*fx for x,y in points]
        opposite_across=-(bx-ax)*fy+(by-ay)*fx
        low,high=sorted((0.0,opposite_across))
        if (min(along)<=along_limit_m and max(along)>=-along_limit_m and
                min(across)<=high and max(across)>=low):
            matched.append({'source_id':box['source_id'],'label':box['label'],
                            'vertices_xy_m':[list(p) for p in points],
                            'along_interval_m':[min(along),max(along)],
                            'across_interval_m':[min(across),max(across)]})
    return {'method':'Native opposing-lane widths and mapped divider boxes',
            'road_id':int(approach.road_id),
            'approach_lane_id':int(approach.lane_id),
            'opposite_lane_id':int(opposite.lane_id),
            'approach_xy_m':[ax,ay],
            'opposite_xy_m':[bx,by],
            'approach_forward_unit_xy':[fx,fy],
            'lane_center_separation_m':separation,
            'lane_widths_m':list(widths),
            'unoccupied_lane_edge_gap_m':gap,
            'nearby_divider_boxes':matched,
            'divided_highway_legal_judgment':None,
            'public_authority_opening_status':None,
            'crossover_or_intersection_status':None,
            'actual_barrier_crossing_verified':False}


def select_227_candidate(world,carla,*,waypoint_spacing_m=2.0,
                         min_gap_m=1.0,max_candidates=500):
    """Require a visible mapped divider in the opposing-lane median space."""
    from u_turn_construction import select_u_turn_scene
    if not isfinite(min_gap_m) or min_gap_m<=0 or type(max_candidates) is not int or max_candidates<=0:
        raise ValueError('Invalid 227 physical candidate screen')
    boxes=collect_native_dividers(world,carla)
    mapping=world.get_map()
    for index in range(max_candidates):
        try:
            scene=select_u_turn_scene(mapping,waypoint_spacing_m=waypoint_spacing_m,
                                      candidate_index=index)
        except ValueError as error:
            if 'No requested Native opposing-lane U-turn pair' in str(error):
                break
            raise
        report=measure_divider_candidate(scene,boxes)
        if report['unoccupied_lane_edge_gap_m']>=min_gap_m and report['nearby_divider_boxes']:
            report['candidate_index']=index
            return scene,report
    raise ValueError('No Native 227 divider site with opposing lanes and mapped barrier')

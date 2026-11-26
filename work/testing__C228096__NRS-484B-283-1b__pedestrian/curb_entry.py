"""Source-gated curb departure and vehicle-path entry probes."""
from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    name: str
    action: str
    vehicle_gap: str
    route_kind: str
    departure_hold_s: float | None = None
    vehicle_start_gap_m: float | None = None


CASES = (
    Case('close_walk_into_path', 'walk', 'close', 'path'),
    Case('close_run_into_path', 'run', 'close', 'path'),
    Case('far_walk_into_path', 'walk', 'far', 'path'),
    Case('close_walk_road_only', 'walk', 'close', 'road_only'),
    Case('close_walk_remain_curb', 'walk', 'close', 'curb'),
    Case('sudden_departure-0000', 'walk', 'close', 'path', departure_hold_s=4.0),
    Case('sudden_departure-0001', 'walk', 'close', 'path', departure_hold_s=8.0),
    Case('sudden_departure-0002', 'walk', 'close', 'path', departure_hold_s=6.0),
    Case('yield_impossibility-0000', 'walk', 'close', 'path', vehicle_start_gap_m=10.0),
    Case('yield_impossibility-0001', 'walk', 'close', 'path', vehicle_start_gap_m=30.0),
    Case('yield_impossibility-0002', 'walk', 'close', 'path', vehicle_start_gap_m=20.0),
)


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    return type(value) in (int, float) and isfinite(value)


def point(value):
    return isinstance(value, (list, tuple)) and len(value) == 2 and all(number(x) for x in value)


def rect(value):
    return (isinstance(value, (list, tuple)) and len(value) == 4 and
            all(number(x) for x in value) and value[0] < value[2] and
            value[1] < value[3])


def inside(p, box):
    require(point(p) and rect(box), 'position/road geometry missing')
    return box[0] <= p[0] <= box[2] and box[1] <= p[1] <= box[3]


def validate_scene(scene: Mapping, case: Case):
    require(case in CASES, 'unknown exact curb entry case')
    require(scene.get('cell_id') == 'C228096' and
            scene.get('actor') == 'pedestrian' and
            scene.get('pedestrian_person') is True and
            scene.get('vehicle_qualifies') is True and
            scene.get('driver_in_control') is True,
            'qualifying pedestrian/driver/vehicle missing')
    require(scene.get('action') == case.action and
            scene.get('vehicle_gap') == case.vehicle_gap and
            scene.get('route_kind') == case.route_kind,
            'case variables changed')
    for field in ('pedestrian_identity', 'curb_safety', 'road_boundary',
                  'vehicle_path', 'vehicle_motion', 'driver_control',
                  'pedestrian_route', 'departure_timing',
                  'introductory_exceptions'):
        require(scene.get(field + '_source_sha256'),
                'original context missing: ' + field)
    require(rect(scene.get('road_rect_m')) and
            rect(scene.get('vehicle_path_rect_m')) and
            point(scene.get('curb_start_xy')) and
            not inside(scene['curb_start_xy'],scene['road_rect_m']),
            'curb/road/path geometry missing')
    for field in ('pedestrian_route_xy', 'vehicle_route_xy'):
        route = scene.get(field)
        require(isinstance(route, list) and len(route) >= 2 and
                all(point(p) for p in route), field + ' missing')
    require(scene.get('pedestrian_route_xy')[0] == scene.get('curb_start_xy'),
            'pedestrian must depart curb source')
    route = scene['pedestrian_route_xy']
    in_road = [inside(p, scene['road_rect_m']) for p in route]
    in_path = [inside(p, scene['vehicle_path_rect_m']) for p in route]
    if case.route_kind == 'path':
        require(any(in_road) and any(in_path) and in_path[-1],
                'requested vehicle-path route not constructed')
    elif case.route_kind == 'road_only':
        require(any(in_road) and not any(in_path),
                'road-only route enters vehicle path or misses road')
    else:
        require(not any(in_road) and not any(in_path),
                'curb-stay route leaves place of safety')
    require(type(scene.get('departure_frame')) is int and
            0 < scene['departure_frame'] < 900,
            'source-reviewed departure frame missing')
    if case.departure_hold_s is not None:
        require(scene['departure_frame'] == round(case.departure_hold_s * 20),
                'selected departure hold controller differs')
    if case.vehicle_start_gap_m is not None:
        require(scene['vehicle_route_xy'][0] == [-case.vehicle_start_gap_m, 0],
                'selected vehicle station controller differs')
    require(scene.get('vehicle_id') and scene.get('driver_id'),
            'control vehicle/driver identity missing')
    return {'case_id':case.name,'suddenness_judgment':None,
            'impossible_to_yield_judgment':None,
            'introductory_exception_judgment':None}


def construct(adapter,scene:Mapping,case:Case):
    context=validate_scene(scene,case)
    owned=[]
    try:
        ped=adapter.spawn_pedestrian(scene['curb_start_xy'])
        require(ped is not None,'pedestrian spawn failed')
        owned.append(ped)
        vehicle=adapter.spawn_vehicle(scene['vehicle_route_xy'][0])
        require(vehicle is not None,'vehicle spawn failed')
        owned.append(vehicle)
        adapter.set_pedestrian_route(ped,scene['pedestrian_route_xy'],
                                     case.action,scene['departure_frame'])
        adapter.set_vehicle_route(vehicle,scene['vehicle_route_xy'],
                                  case.vehicle_gap)
        return {'owned':tuple(owned),**context}
    except Exception:
        for actor in reversed(owned):adapter.destroy(actor)
        raise


def measure_original(rows:list[Mapping],scene:Mapping,case:Case):
    validate_scene(scene,case)
    require(len(rows)==900,'original 900-frame capture missing')
    first=rows[0].get('original_frame')
    require(type(first) is int and number(rows[0].get('time_s')),
            'original frame/time identity missing')
    ped_id=vehicle_id=None
    road_frame=path_frame=None
    departure_distance=None
    speed_pairs=[]
    for i,row in enumerate(rows):
        require(row.get('original_frame')==first+i and
                number(row.get('time_s')) and
                abs(row['time_s']-rows[0]['time_s']-i/20)<=.005,
                'original frame/time join invalid')
        for field in ('frame','pedestrian_motion','vehicle_motion',
                      'road_boundary','curb_safety','vehicle_path',
                      'driver_control','introductory_exceptions'):
            require(row.get(field+'_source_sha256'),
                    'original measurement source missing: '+field)
        require(row.get('vehicle_path_source_sha256')==
                scene['vehicle_path_source_sha256'] and
                row.get('action')==case.action,
                'original path/action context changed')
        require(row.get('pedestrian_id') and row.get('vehicle_id'),
                'participant identity missing')
        ped_id=ped_id or row['pedestrian_id'];vehicle_id=vehicle_id or row['vehicle_id']
        require(row['pedestrian_id']==ped_id and row['vehicle_id']==vehicle_id and
                ped_id!=vehicle_id,'participant identity changed')
        require(point(row.get('pedestrian_xy')) and point(row.get('vehicle_xy')) and
                number(row.get('pedestrian_speed_mps')) and
                number(row.get('vehicle_speed_mps')),
                'original synchronized motion missing')
        in_road=inside(row['pedestrian_xy'],scene['road_rect_m'])
        in_path=inside(row['pedestrian_xy'],scene['vehicle_path_rect_m'])
        if i==0:require(not in_road and not in_path,'pedestrian not initially safe')
        if road_frame is None and in_road:
            road_frame=first+i
            departure_distance=hypot(row['pedestrian_xy'][0]-row['vehicle_xy'][0],
                                     row['pedestrian_xy'][1]-row['vehicle_xy'][1])
        if path_frame is None and in_path:path_frame=first+i
        speed_pairs.append((row['pedestrian_speed_mps'],row['vehicle_speed_mps']))
    if case.route_kind=='path':
        require(road_frame is not None and path_frame is not None and
                road_frame<=path_frame,'road and vehicle-path entry missing')
    elif case.route_kind=='road_only':
        require(road_frame is not None and path_frame is None,
                'road-only control entered vehicle path')
    else:
        require(road_frame is None and path_frame is None,
                'curb-stay control left safety')
    return {'case_id':case.name,'road_entry_frame':road_frame,
            'vehicle_path_entry_frame':path_frame,
            'vehicle_distance_at_road_entry_m':departure_distance,
            'maximum_pedestrian_speed_mps':max(x for x,_ in speed_pairs),
            'maximum_vehicle_speed_mps':max(y for _,y in speed_pairs),
            'suddenness_judgment':None,'impossible_to_yield_judgment':None,
            'introductory_exception_judgment':None}

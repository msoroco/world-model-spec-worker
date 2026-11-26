"""Exact source-gated sidewalk vehicle placement and exception-context probes."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping

from sidewalk_footprint import _area, _clip, _convex, _points


@dataclass(frozen=True)
class Case:
    case_id: str
    relation: str
    traffic_context: str


CASES = (
    Case('park_on_sidewalk', 'overlap', 'absent'),
    Case('park_edge_touch', 'touch', 'absent'),
    Case('park_off_sidewalk', 'separate', 'absent'),
    Case('on_sidewalk_traffic_necessity', 'overlap', 'unresolved'),
)

EXCEPTIONS = ('traffic_conflict_necessity', 'law_compliance', 'officer_direction',
              'official_device_direction', 'subsection_3')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def area_intersection(a, b):
    polygon = _clip(_points(a), _points(b))
    return abs(_area(polygon)) if len(polygon) >= 3 else 0.0


def point_segment_distance(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0., min(1., ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def boundary_distance(a, b):
    return min(point_segment_distance(p,b[i],b[(i+1)%len(b)]) for p in a for i in range(len(b)))


def validate_site(site: Mapping):
    require(site.get('cell_id') == 'C229462' and site.get('actor') == 'motor_vehicle_driver',
            'wrong exact sidewalk cell or actor')
    for name in ('jurisdiction', 'highway_status', 'curb', 'lateral_highway_lines',
                 'property_lines', 'pedestrian_use', 'map', 'sidewalk_polygon',
                 'vehicle_blueprint', 'approach_route', 'parking_purpose',
                 'exception_context', 'conflict_vehicle_motion'):
        require(site.get(name + '_source_sha256'), 'original sidewalk source missing: ' + name)
    sidewalk = _points(site.get('sidewalk_polygon_xy'))
    require(_convex(sidewalk) and abs(_area(sidewalk)) > 1e-6,
            'source-bound sidewalk polygon invalid')
    route = site.get('approach_route_xy')
    require(isinstance(route,list) and len(route)>=2 and
            all(isinstance(p,list) and len(p)==2 and all(type(v) in (int,float) and isfinite(v) for v in p) for p in route),
            'reviewed parking approach missing')
    targets = site.get('target_footprints')
    require(isinstance(targets,dict) and set(targets)=={'overlap','touch','separate'},
            'three source-bound target footprints required')
    for name, item in targets.items():
        polygon = _points(item.get('polygon_xy'))
        require(_convex(polygon) and abs(_area(polygon))>1e-6 and item.get('source_sha256'),
                'source-bound sidewalk target invalid: '+name)
    exceptions = site.get('exception_context')
    require(isinstance(exceptions,dict) and all(exceptions.get(x) in ('present','absent','unresolved') for x in EXCEPTIONS),
            'independent statutory exception context required')
    if exceptions['traffic_conflict_necessity']=='unresolved':
        for name in ('conflict_vehicle_start_xy','conflict_vehicle_end_xy'):
            value=site.get(name)
            require(isinstance(value,list) and len(value)==2 and
                    all(type(v) in (int,float) and isfinite(v) for v in value),
                    'reviewed traffic vehicle path missing: '+name)
    return {'sidewalk_area_id':site.get('sidewalk_area_id'),
            'exception_context':exceptions, 'legal_judgment':None}


def construct(adapter, site: Mapping, case: Case):
    validate_site(site)
    require(case in CASES, 'unknown exact sidewalk case')
    require(site['requested_relation']==case.relation and
            site['exception_context']['traffic_conflict_necessity']==case.traffic_context,
            'reviewed sidewalk target or traffic context differs')
    owned=[]
    try:
        ego=adapter.spawn_vehicle(site['approach_route_xy'][0], 'ego')
        require(ego is not None,'ego spawn failed')
        owned.append(ego)
        if case.traffic_context!='absent':
            other=adapter.spawn_vehicle(site['conflict_vehicle_start_xy'],'conflict')
            require(other is not None,'conflict participant spawn failed')
            owned.append(other)
        adapter.set_parking_route(ego,site['approach_route_xy'],
                                  site['target_footprints'][case.relation]['polygon_xy'])
        adapter.request_parking(ego)
        return {'case_id':case.case_id,'ego':ego,'owned':tuple(owned),'legal_judgment':None}
    except Exception:
        for actor in reversed(owned):adapter.destroy(actor)
        raise


def measure_original(rows: list[Mapping], site: Mapping, case: Case):
    validate_site(site)
    require(case in CASES and len(rows)==900,'exact 900-frame sidewalk case missing')
    require(site['requested_relation']==case.relation,'selected sidewalk relation differs')
    first=rows[0].get('original_frame')
    require(type(first) is int,'original frame identity missing')
    ego_id=None
    areas=[];distances=[];speeds=[];activities=[]
    for i,row in enumerate(rows):
        require(row.get('original_frame')==first+i and type(row.get('time_s')) in (int,float) and
                isfinite(row['time_s']) and abs(row['time_s']-rows[0]['time_s']-i/20)<=.005,
                'original sidewalk frame/time join invalid')
        for name in ('source_sha256','body_geometry_source_sha256','activity_source_sha256',
                     'sidewalk_source_sha256','exception_source_sha256'):
            require(row.get(name),'original sidewalk source missing: '+name)
        require(row['sidewalk_source_sha256']==site['sidewalk_polygon_source_sha256'],
                'original sidewalk geometry source changed')
        require(row.get('ego_id'),'original ego identity missing')
        ego_id=ego_id or row['ego_id']
        require(row['ego_id']==ego_id and row.get('vehicle_type')=='motor_vehicle',
                'motor vehicle identity changed')
        body=_points(row.get('vehicle_body_polygon_xy'))
        require(_convex(body) and abs(_area(body))>1e-6,'original body footprint invalid')
        area=area_intersection(body,site['sidewalk_polygon_xy'])
        areas.append(area);distances.append(boundary_distance(body,site['sidewalk_polygon_xy']))
        speed=row.get('ego_speed_mps')
        require(type(speed) in (int,float) and isfinite(speed),'original speed missing')
        speeds.append(speed)
        activity=row.get('observed_activity')
        require(activity in ('approach','park','stop','stand'),'original parking activity missing')
        activities.append(activity)
        require(row.get('exception_context')==site['exception_context'],
                'original statutory exception context changed')
        if case.traffic_context=='unresolved':
            require(row.get('conflict_vehicle_id') and row.get('conflict_motion_source_sha256'),
                    'original traffic-conflict vehicle motion absent')
    require(max(speeds[-20:])<=.1 and set(activities[-20:])=={'park'},
            'terminal original parking conduct absent')
    overlap=sum(areas[-20:])/20
    distance=min(distances[-20:])
    if case.relation=='overlap':
        require(overlap>1e-6,'positive original sidewalk body overlap absent')
    else:
        require(overlap<=1e-6,'original sidewalk body overlap not isolated')
        if case.relation=='touch':
            require(distance<=.05,'original sidewalk boundary touch absent')
        else:
            require(distance>.05,'original off-sidewalk separation absent')
    return {'case_id':case.case_id,'frame_count':900,
            'terminal_mean_sidewalk_body_overlap_m2':overlap,
            'terminal_boundary_distance_m':distance,
            'observed_activity':'park','traffic_conflict_necessity':case.traffic_context,
            'exception_context':site['exception_context'],
            'sidewalk_status_judgment':None,'traffic_necessity_judgment':None,
            'legal_judgment':None}

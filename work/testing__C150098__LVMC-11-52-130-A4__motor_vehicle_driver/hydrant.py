"""C150098 physical hydrant construction and original-frame distance probes.

Longitudinal body-to-hydrant gap is an engineering observation, not an adopted
legal distance convention. Actual statutory classification stays unresolved.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

ASSIGNMENT = 'testing__C150098__LVMC-11-52-130-A4__motor_vehicle_driver'
FEET_15_M = 4.572


@dataclass(frozen=True)
class Case:
    suffix: str
    side: str
    gap_m: float
    activity: str = 'park'
    exception: str = 'none'


CASES = (
    Case('upstream_inside', 'upstream', 4.422),
    Case('upstream_at', 'upstream', FEET_15_M),
    Case('upstream_outside', 'upstream', 4.722),
    Case('downstream_inside', 'downstream', 4.422),
    Case('downstream_at', 'downstream', FEET_15_M),
    Case('downstream_outside', 'downstream', 4.722),
    Case('upstream_stop', 'upstream', 4.422, 'stop'),
    Case('upstream_stand', 'upstream', 4.422, 'stand'),
    Case('upstream_traffic_exception', 'upstream', 4.422, 'stop', 'lawful_traffic_conflict'),
    Case('upstream_police_exception', 'upstream', 4.422, 'stop', 'police_direction'),
    Case('upstream_device_exception', 'upstream', 4.422, 'stop', 'traffic_device_direction'),
)


def need(ok, message):
    if not ok:
        raise ValueError(message)


def finite(x):
    return type(x) in (int, float) and isfinite(x)


def validate_site(site: Mapping):
    need(site.get('assignment_id') == ASSIGNMENT and site.get('cell_id') == 'C150098'
         and site.get('layout') == 'one_way_road' and site.get('control') == 'fire_hydrant',
         'wrong hydrant assignment or fixed cell')
    for key in ('map_sha256', 'municipal_jurisdiction_sha256',
                'parallel_parking_authority_sha256', 'hydrant_identity_sha256',
                'hydrant_geometry_sha256', 'hydrant_blueprint_sha256',
                'curb_source_sha256', 'one_way_direction_sha256',
                'ego_blueprint_sha256', 'camera_plan_sha256'):
        need(bool(site.get(key)), key+' source missing')
    need(site.get('parallel_parking_permitted') is True,
         'location-specific parallel parking permission missing')
    need(site.get('hydrant_physical_support') in ('map_object','spawned_prop'),
         'physical hydrant support missing')
    hydrant = site.get('hydrant')
    need(isinstance(hydrant, dict) and all(finite(hydrant.get(k)) for k in
         ('west_x_m','east_x_m','curb_y_m','depth_m')),
         'hydrant source geometry invalid')
    need(hydrant['east_x_m'] > hydrant['west_x_m'] and hydrant['depth_m'] > 0,
         'hydrant extent invalid')
    waypoints = site.get('approach_waypoints')
    need(isinstance(waypoints,list) and len(waypoints)>=2 and
         all(isinstance(p,list) and len(p)==2 and all(finite(v) for v in p)
             for p in waypoints), 'one-way route source missing')
    need(waypoints[0][0] < waypoints[-1][0], 'one-way route direction reversed')
    for key in ('property_status','sign_status','red_paint_status'):
        need(site.get(key) in ('public','private','unknown') if
             key=='property_status' else site.get(key) in ('present','absent','unknown'),
             key+' observation missing')


def target_interval(site: Mapping, case: Case, body_length_m: float):
    need(case in CASES and finite(body_length_m) and body_length_m > 0,
         'case or body length invalid')
    hydrant = site['hydrant'];west,east=hydrant['west_x_m'],hydrant['east_x_m']
    if case.side=='upstream':
        return (west-case.gap_m-body_length_m, west-case.gap_m)
    return (east+case.gap_m,east+case.gap_m+body_length_m)


def build_case(adapter, site: Mapping, case: Case, body_length_m: float):
    """Create/read physical hydrant and vehicle via a lazy CARLA adapter."""
    validate_site(site)
    interval = target_interval(site,case,body_length_m)
    owned=[]
    try:
        if site['hydrant_physical_support']=='spawned_prop':
            hydrant=adapter.spawn_hydrant(site['hydrant'],
                                          blueprint_sha256=site['hydrant_blueprint_sha256'])
            need(hydrant is not None,'physical hydrant spawn failed')
            owned.append(hydrant)
        else:
            hydrant=adapter.lookup_hydrant(site['hydrant_identity_sha256'])
            need(hydrant is not None,'mapped physical hydrant missing')
        readback=adapter.read_hydrant(hydrant)
        need(readback.get('identity_sha256')==site['hydrant_identity_sha256'] and
             readback.get('geometry_sha256')==site['hydrant_geometry_sha256'] and
             readback.get('physically_present') is True,
             'physical hydrant readback differs')
        ego=adapter.spawn_vehicle(site['approach_waypoints'][0],
                                  blueprint_sha256=site['ego_blueprint_sha256'])
        need(ego is not None,'ego vehicle spawn failed')
        owned.append(ego)
        adapter.set_route(ego,site['approach_waypoints'],one_way=True)
        adapter.set_curb_target(ego,interval,site['hydrant']['curb_y_m'],activity=case.activity)
        if case.exception!='none':
            source_key={'lawful_traffic_conflict':'traffic_conflict_source_sha256',
                        'police_direction':'police_direction_source_sha256',
                        'traffic_device_direction':'traffic_device_source_sha256'}[case.exception]
            need(site.get(source_key),case.exception+' source missing')
            adapter.set_exception_source(ego,case.exception,site[source_key])
        return {'case_id':ASSIGNMENT+'__'+case.suffix,'ego':ego,'hydrant':hydrant,
                'target_body_interval_m':interval,'owned':tuple(owned)}
    except Exception:
        for actor in reversed(owned):
            adapter.destroy(actor)
        raise


def gap(body_west,body_east,hydrant_west,hydrant_east):
    if body_east < hydrant_west:return 'upstream',hydrant_west-body_east
    if body_west > hydrant_east:return 'downstream',body_west-hydrant_east
    return 'overlap',0.0


def measure_original_history(rows,site: Mapping,case: Case):
    validate_site(site)
    need(case in CASES and len(rows)>=2,'case or original history missing')
    fixed={key:rows[0].get(key) for key in
           ('actor_id','hydrant_actor_id','map_sha256','site_sha256',
            'hydrant_identity_sha256','hydrant_geometry_sha256',
            'parallel_parking_authority_sha256','camera_plan_sha256')}
    need(all(fixed.values()),'original fixed source missing')
    for key in ('map_sha256','hydrant_identity_sha256','hydrant_geometry_sha256',
                'parallel_parking_authority_sha256','camera_plan_sha256'):
        need(fixed[key]==site[key],'original site source differs: '+key)
    first=rows[0].get('frame');need(type(first) is int,'original frame identity missing')
    observed=[];previous_time=None
    for i,row in enumerate(rows):
        time=row.get('time_s')
        need(row.get('case_id')==ASSIGNMENT+'__'+case.suffix and
             row.get('frame')==first+i and finite(time),
             'original case/frame/time identity differs')
        if previous_time is not None:
            need(.049 <= time-previous_time <= .051,'original 20 Hz time gap')
        previous_time=time
        need(all(row.get(key)==value for key,value in fixed.items()),'original source changed')
        need(row.get('hydrant_physically_present') is True and
             bool(row.get('body_source_sha256')) and bool(row.get('frame_map_sha256')),
             'physical hydrant or original body source missing')
        west,east=row.get('body_west_x_m'),row.get('body_east_x_m')
        need(finite(west) and finite(east) and east>west,'original body extent invalid')
        need(row.get('activity_observation') in ('moving','stopped','standing','parked'),
             'activity observation missing')
        need(row.get('exception_kind')==case.exception,
             'exception source classification differs')
        if case.exception!='none':
            need(bool(row.get('exception_source_sha256')),'exception source missing')
        side,distance=gap(west,east,site['hydrant']['west_x_m'],site['hydrant']['east_x_m'])
        observed.append({'frame':first+i,'time_s':time,'side':side,
                         'longitudinal_body_hydrant_gap_m':distance,
                         'activity':row['activity_observation']})
    return {'case_id':ASSIGNMENT+'__'+case.suffix,'frame_count':len(rows),
            'first_frame':first,'last_frame':first+len(rows)-1,
            'source_identity':fixed,'observed':observed,
            'minimum_longitudinal_gap_m':min(x['longitudinal_body_hydrant_gap_m'] for x in observed),
            'fifteen_feet_m_reference':FEET_15_M,
            'legal_distance_convention':'unresolved_review','legal_verdict_claimed':False}

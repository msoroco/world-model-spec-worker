"""Exact source-gated driveway sidewalk entry and pedestrian contrast."""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Mapping


@dataclass(frozen=True)
class Case:
    case_id: str
    stop: bool
    pedestrian: bool
    yield_to_pedestrian: bool


CASES = (
    Case('stops_pedestrian', True, True, True),
    Case('no_stop_pedestrian', False, True, False),
    Case('stops_no_pedestrian', True, False, False),
    Case('stops_pedestrian_no_yield', True, True, False),
)

SOURCE_ROLES = ('jurisdiction','district','district_frontage','driveway_permission',
                'access_type','map','sidewalk_area','sidewalk_edge','vehicle_class',
                'vehicle_blueprint','approach_route','stop_point','pedestrian_route',
                'pedestrian_conflict_region','operator_yield_plan')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def point(value, name):
    require(isinstance(value,list) and len(value)==2 and
            all(type(x) in (int,float) and isfinite(x) for x in value),
            'reviewed coordinate missing: '+name)
    return value


def signed_distance(xy, site):
    x,y=point(xy,'position')
    edge=site['edge_point_xy'];normal=site['edge_normal_xy']
    return (edge[0]-x)*normal[0]+(edge[1]-y)*normal[1]


def validate_site(site: Mapping):
    require(site.get('cell_id')=='C213645' and site.get('actor')=='cycle_or_scooter_operator',
            'wrong exact driveway cell or actor')
    for role in SOURCE_ROLES:
        require(site.get(role+'_source_sha256'),'original driveway source missing: '+role)
    require(site.get('district_type')=='residence' and site.get('access_type')=='driveway',
            'selected residence driveway source absent')
    require(site.get('vehicle_type') in ('bicycle','electric_bicycle','electric_scooter'),
            'qualifying cycle or scooter source absent')
    require(site.get('vehicle_blueprint_id') and site.get('map_id') and site.get('sidewalk_area_id'),
            'reviewed Native map, vehicle or sidewalk identity missing')
    point(site.get('edge_point_xy'),'sidewalk edge')
    normal=point(site.get('edge_normal_xy'),'edge normal')
    require(abs(hypot(*normal)-1)<.01,'reviewed edge normal must be unit length')
    route=site.get('approach_route_xy')
    require(isinstance(route,list) and len(route)>=3,'reviewed driveway route missing')
    for i,xy in enumerate(route):point(xy,'route '+str(i))
    require(signed_distance(route[0],site)>0 and signed_distance(route[-1],site)<0,
            'reviewed route does not cross sidewalk edge')
    require(type(site.get('ego_spawn_z')) in (int,float) and isfinite(site['ego_spawn_z']),
            'reviewed cycle spawn height missing')
    require(type(site.get('pedestrian_spawn_z')) in (int,float) and isfinite(site['pedestrian_spawn_z']) and
            site.get('pedestrian_blueprint_id'), 'reviewed pedestrian spawn missing')
    point(site.get('pedestrian_conflict_center_xy'),'pedestrian conflict center')
    require(type(site.get('pedestrian_conflict_radius_m')) in (int,float) and
            site['pedestrian_conflict_radius_m']>0, 'pedestrian conflict radius missing')
    require(type(site.get('pedestrian_speed_mps')) in (int,float) and
            site['pedestrian_speed_mps']>0, 'pedestrian speed missing')
    point(site.get('stop_point_xy'),'pre-entry stop point')
    require(signed_distance(site['stop_point_xy'],site)>0,'stop point is not before sidewalk edge')
    ped=site.get('pedestrian_route_xy')
    require(isinstance(ped,list) and len(ped)>=2,'reviewed pedestrian route missing')
    for i,xy in enumerate(ped):point(xy,'pedestrian '+str(i))
    require(site.get('requested_stop') in (True,False) and
            site.get('requested_pedestrian') in (True,False) and
            site.get('requested_yield') in (True,False),'reviewed contrast parameters missing')
    require(not site['requested_yield'] or site['requested_pedestrian'],
            'cannot request yield without pedestrian')
    return {'legal_judgment':None,'immediate_proximity_judgment':None,
            'collision_necessity_judgment':None}


def validate_case(site,case):
    validate_site(site)
    require(case in CASES,'unknown exact driveway case')
    require((site['requested_stop'],site['requested_pedestrian'],site['requested_yield'])==
            (case.stop,case.pedestrian,case.yield_to_pedestrian),
            'reviewed driveway contrast differs from case')


def measure_original(rows,site,case):
    validate_case(site,case)
    require(len(rows)==900,'exact 900-frame driveway history missing')
    first=rows[0].get('original_frame')
    require(type(first) is int,'original frame identity missing')
    actor=None;pedestrian_ids=set()
    for i,row in enumerate(rows):
        require(row.get('original_frame')==first+i and type(row.get('time_s')) in (int,float) and
                isfinite(row['time_s']) and abs(row['time_s']-rows[0]['time_s']-i/20)<=.005,
                'original driveway frame/time join invalid')
        for name in ('source_sha256','vehicle_motion_source_sha256','edge_source_sha256',
                     'pedestrian_motion_source_sha256','yield_source_sha256'):
            require(row.get(name),'original driveway source missing: '+name)
        require(row['edge_source_sha256']==site['sidewalk_edge_source_sha256'],
                'original sidewalk edge source changed')
        require(row.get('ego_id') and row.get('vehicle_type')==site['vehicle_type'],
                'original qualifying operator identity missing')
        actor=actor or row['ego_id'];require(row['ego_id']==actor,'operator identity changed')
        require(type(row.get('speed_mps')) in (int,float) and isfinite(row['speed_mps']) and row['speed_mps']>=0,
                'original speed missing')
        require(type(row.get('distance_before_sidewalk_edge_m')) in (int,float) and
                isfinite(row['distance_before_sidewalk_edge_m']),'original edge distance missing')
        require(isinstance(row.get('pedestrian_in_conflict_area'),bool) and
                isinstance(row.get('operator_yield_observed'),bool),
                'original pedestrian/yield readback missing')
        ids=row.get('pedestrian_actor_ids')
        require(isinstance(ids,list),'original pedestrian IDs missing')
        pedestrian_ids.update(ids)
    entries=[i for i in range(1,900) if rows[i]['distance_before_sidewalk_edge_m']<=0<rows[i-1]['distance_before_sidewalk_edge_m']]
    require(len(entries)==1,'one original sidewalk entry bracket required')
    entry=entries[0]
    moving=next((i for i in range(entry) if rows[i]['speed_mps']>.5),None)
    require(moving is not None,'original driveway approach motion absent')
    stops=[i for i in range(moving+1,entry) if rows[i]['speed_mps']<=.1]
    last_stop=stops[-1] if stops else None
    require((last_stop is not None)==case.stop,'actual pre-entry stop contrast absent')
    conflict=any(row['pedestrian_in_conflict_area'] for row in rows[max(0,entry-20):entry+21])
    require(conflict==case.pedestrian,'actual pedestrian conflict contrast absent')
    if case.pedestrian:require(pedestrian_ids,'actual pedestrian participant absent')
    yielded=any(row['operator_yield_observed'] for row in rows[max(0,entry-60):entry+1])
    require(yielded==case.yield_to_pedestrian,'actual yield contrast absent')
    return {'case_id':case.case_id,'frame_count':900,'entry_bracket_indices':[entry-1,entry],
            'last_pre_entry_stop_index':last_stop,
            'last_stop_distance_before_edge_m':rows[last_stop]['distance_before_sidewalk_edge_m'] if last_stop is not None else None,
            'pedestrian_conflict_observed':conflict,'pedestrian_actor_ids':sorted(pedestrian_ids),
            'operator_yield_observed':yielded,'immediate_proximity_judgment':None,
            'collision_necessity_judgment':None,'legal_judgment':None}

"""Source-gated Native access-route construction; map road type is insufficient."""
import math
from package_spec import AID
from access_probe import validate_site

CASES = {'indicated_entry': ('entry', True, True), 'unindicated_entry': ('entry', False, True), 'notice_not_visible': ('entry', True, False), 'indicated_exit': ('exit', True, True), 'unindicated_exit': ('exit', False, True)}

def number(value):
    if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value):
        raise ValueError('finite numeric source value required')
    return float(value)

def construct(site, case):
    if site.get('assignment_id') != AID or site.get('case_id') != case or site.get('source_kind') != 'original_native_access_survey' or site.get('reviewed_original_native_site') is not True:
        raise ValueError('exact reviewed original Native access site required')
    suffix = case.removeprefix(AID + '__')
    if suffix not in CASES:
        raise ValueError('unknown exact access case')
    direction, indicated, visible = CASES[suffix]
    for key in ('source_id','map_name','map_sha256','authority_source','highway_source','boundary_source','official_notice_source','driver_actor_id'):
        if not site.get(key):
            raise ValueError('separate source fact absent: '+key)
    if site.get('public_highway') is not True or site.get('controlled_access_determination') is not True or site.get('authority_designated_devices') is not True:
        raise ValueError('public authority controlled-access and official device designation required')
    if site.get('map_road_type_as_legal_source') is True:
        raise ValueError('map road type cannot establish legal controlled-access status')
    if site.get('requested_direction') != direction or site.get('requested_indicated') is not indicated or site.get('requested_notice_visible') is not visible:
        raise ValueError('case-specific access request differs')
    probe = {'authority_source':site['authority_source'],'highway_source':site['highway_source'],'boundary_source':site['boundary_source'],'controlled_access_determination':True,'boundary_x_m':site.get('boundary_x_m'),'indicated_points':site.get('indicated_points'),'official_notice_source':site['official_notice_source'],'vehicle_id':site['driver_actor_id']}
    validate_site(probe)
    point = site.get('target_point')
    if not isinstance(point,dict) or point.get('direction') != direction or point.get('indicated') is not indicated or point.get('notice_visible') is not visible or not point.get('source_ref'):
        raise ValueError('source-backed exact target crossing point required')
    y = number(point.get('crossing_y_m'))
    matches = [p for p in probe['indicated_points'] if p['direction']==direction and p['y_min_m']<=y<=p['y_max_m']]
    if indicated and (len(matches)!=1 or matches[0]['notice_visible'] is not visible or matches[0]['point_id']!=point.get('point_id')):
        raise ValueError('official indicated access point or visibility differs')
    if not indicated and matches:
        raise ValueError('unindicated crossing overlaps designated point')
    spawn=site.get('native_spawn')
    if not isinstance(spawn,dict) or not spawn.get('source_id') or not spawn.get('blueprint_id') or not isinstance(spawn.get('pose_xyz_ypr'),list) or len(spawn['pose_xyz_ypr'])!=6:
        raise ValueError('source-backed Native vehicle pose required')
    for value in spawn['pose_xyz_ypr']:number(value)
    route=site.get('trajectory')
    if not isinstance(route,dict) or not route.get('source_id') or not isinstance(route.get('points_xy'),list) or len(route['points_xy'])<3:
        raise ValueError('source-backed drivable route required')
    points=route['points_xy']
    for xy in points:
        if not isinstance(xy,list) or len(xy)!=2:raise ValueError('route xy source required')
        for value in xy:number(value)
    b=probe['boundary_x_m']
    if (points[0][0]<b<points[-1][0]) != (direction=='entry') or (points[0][0]>b>points[-1][0]) != (direction=='exit'):
        raise ValueError('source route does not cross boundary in exact direction')
    return {'case_id':case,'direction':direction,'indicated':indicated,'notice_visible':visible,'crossing_y_m':y,'trajectory_xy':points,'probe_site':probe,'native_readback_required':True}

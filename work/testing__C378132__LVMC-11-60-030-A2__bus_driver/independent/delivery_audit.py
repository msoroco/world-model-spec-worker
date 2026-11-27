"""Independent original A2 delivery audit; prepared fixtures are never accepted."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ASSIGNMENT='testing__C378132__LVMC-11-60-030-A2__bus_driver'
VIEWS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')
PERMITTED=('bus_stop','bus_stand','passenger_loading_zone','route_origin','route_destination')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inside(point,polygon):
    x,y=point;hit=False
    for i in range(len(polygon)):
        x1,y1=polygon[i-1];x2,y2=polygon[i]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:
            hit=not hit
    return hit


def body_relation(body,polygon):
    flags=[inside(point,polygon) for point in body]
    if all(flags):return 'inside'
    if any(flags):return 'mixed'
    def turn(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def touches(a,b,c,d):
        x,y=turn(a,b,c),turn(a,b,d);u,v=turn(c,d,a),turn(c,d,b)
        for p,q,r in ((a,b,c),(a,b,d),(c,d,a),(c,d,b)):
            if turn(p,q,r)==0 and min(p[0],q[0])<=r[0]<=max(p[0],q[0]) and min(p[1],q[1])<=r[1]<=max(p[1],q[1]):return True
        return (x>0)!=(y>0) and (u>0)!=(v>0)
    if any(touches(body[i-1],body[i],polygon[j-1],polygon[j])
           for i in range(len(body)) for j in range(len(polygon))):return 'mixed'
    if any(inside(point,body) for point in polygon):return 'mixed'
    return 'outside'


def locate(body,polygons):
    states={key:body_relation(body,polygon) for key,polygon in polygons.items()}
    if 'mixed' in states.values():raise ValueError('bus body straddles designated place boundary')
    found=[key for key,value in states.items() if value=='inside']
    if len(found)>1:raise ValueError('bus body overlaps multiple designated places')
    return found[0] if found else 'outside'


def verify(case_id,attempt,source,decode,physical,pixels,activity,designation,core):
    plan=json.loads((Path(__file__).resolve().parents[1]/'case-plan.json').read_text())
    selected=next((case for case in plan['cases'] if case['case_id']==case_id),None)
    if selected is None:raise ValueError('unknown exact A2 loading-stop case')
    attempt=Path(attempt).resolve()
    if source.get('case_id')!=case_id or source.get('passed') is not True or source.get('source_kind')!='original_native_capture':
        raise ValueError('original Native source chain unverified')
    if physical.get('case_id')!=case_id or physical.get('provenance_kind')!='native' or physical.get('diagnostic_fixture') is not False or physical.get('maneuver_completed') is not True:
        raise ValueError('complete original bus arrival, stop and departure unverified')
    checks=physical.get('physical_checks',{})
    if not {'setup','target','maneuver'}<=set(checks):raise ValueError('original physical checks incomplete')
    for item in checks.values():
        if item.get('status')!='met' or not item.get('sources'):raise ValueError('original physical check lacks sources')
        for rel,digest in item['sources'].items():
            path=(attempt/rel).resolve()
            if not path.is_relative_to(attempt) or not path.is_file() or sha(path)!=digest:
                raise ValueError('physical completion source changed: '+rel)
    frame_map=attempt/'video_frames.jsonl'
    rows=[json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes=core.get('scenes',[])
    if len(rows)!=900 or len(scenes)!=900 or source.get('frames')!=900 or source.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('900 original joined bus frames required')
    for i,(row,scene) in enumerate(zip(rows,scenes)):
        if row.get('video_frame')!=i or scene.get('t')!=round(row.get('time_s',-1)*1000):
            raise ValueError('Core/original bus time join differs')
    if decode.get('case_id')!=case_id or decode.get('passed') is not True or set(decode.get('videos',{}))!=set(VIEWS):
        raise ValueError('full four-camera original decode unverified')
    for view in VIEWS:
        video=attempt/(view+'.mkv');item=decode['videos'][view]
        if item.get('frames')!=900 or item.get('sha256')!=sha(video):
            raise ValueError('decoded original camera source changed: '+view)
    if pixels.get('format')!='worker-original-pixel-review' or pixels.get('case_id')!=case_id or pixels.get('diagnostic_fixture') is not False or not pixels.get('reviewer'):
        raise ValueError('independent original pixel review missing')
    if pixels.get('frame_map_sha256')!=sha(frame_map) or pixels.get('video_sha256')!=sha(attempt/'overview.mkv'):
        raise ValueError('original pixel source changed')
    for name in ('bus_body','location_boundary','public_street','designation_signs','loading_activity'):
        item=pixels.get('observations',{}).get(name,{})
        if item.get('visible') is not True or item.get('view') not in VIEWS or not isinstance(item.get('frame'),int) or not 0<=item['frame']<900 or not item.get('description'):
            raise ValueError('actual loading-stop pixels unverified: '+name)
    if designation.get('case_id')!=case_id or designation.get('authority')!='City Traffic Engineer' or not designation.get('reviewer') or designation.get('diagnostic_fixture') is not False:
        raise ValueError('actual official location designation review missing')
    if set(designation.get('designated_locations',[]))!=set(PERMITTED) or designation.get('signs_reviewed') is not True or designation.get('assigned_route_reviewed') is not True:
        raise ValueError('five permitted locations or assigned route unreviewed')
    if designation.get('frame_map_sha256')!=sha(frame_map) or designation.get('site_sha256')!=sha(attempt/'site.json'):
        raise ValueError('designation/original attempt join changed')
    if activity.get('case_id')!=case_id or activity.get('diagnostic_fixture') is not False or not activity.get('reviewer') or activity.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('independent original loading activity review missing')
    for key in ('loading_purpose','stop_reason','bus_class'):
        if activity.get(key)!=selected[key]:raise ValueError('original purpose, exception or bus class differs: '+key)
    if activity.get('complete_interval') is not True:
        raise ValueError('complete original stopped interval unverified')
    interval=activity.get('interval_frames')
    if not isinstance(interval,list) or len(interval)!=2 or not all(isinstance(x,int) for x in interval) or not 0<=interval[0]<interval[1]<900:
        raise ValueError('original stopped interval missing')
    native_path=attempt/'native.json'
    if source.get('native_sha256')!=sha(native_path):
        raise ValueError('original Native bus ledger changed')
    site=json.loads((attempt/'site.json').read_text());native=json.loads(native_path.read_text())
    if site.get('source_class')!='original_independent_review' or site.get('public_street') is not True or site.get('cell_id')!='C378132':
        raise ValueError('original public-street site missing')
    polygons=site.get('location_polygons_xy_m')
    if not isinstance(polygons,dict) or set(polygons)!=set(PERMITTED):
        raise ValueError('five source-reviewed location boundaries missing')
    frames=native.get('frames',[])
    if len(frames)!=900:raise ValueError('original Native bus history incomplete')
    observed=[]
    for i in range(interval[0],interval[1]+1):
        row=frames[i]
        if row.get('frame')!=i or row.get('time_s')!=i/20 or row.get('bus_speed_mps',99)>.2:
            raise ValueError('bus did not remain stopped over original interval')
        location=locate(row.get('bus_footprint_xy_m',[]),polygons)
        if row.get('measured_location')!=location:
            raise ValueError('original footprint/location measurement changed')
        observed.append(location)
    if set(observed)!={selected['location_kind']}:
        raise ValueError('original stopped body/location differs from selected probe')
    return {'format':'worker-bus-loading-stop-delivery-audit','passed':True,'case_id':case_id,
            'checks':{key:True for key in CHECKS},'frames':900,
            'frame_map_sha256':sha(frame_map),
            'location_kind':selected['location_kind'],'loading_purpose':selected['loading_purpose'],
            'stop_reason':selected['stop_reason'],'bus_class':selected['bus_class'],
            'legal_verdict':None}

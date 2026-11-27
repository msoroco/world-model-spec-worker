"""Independent original bus-stop location audit; synthetic sources cannot pass."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ASSIGNMENT='testing__C386411__LVMC-11-60-030-A1__bus_driver'
SUFFIXES=('stand_inside','stand_outside','park_inside','park_outside')
VIEWS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inside(point,polygon):
    x,y=point;hit=False
    for i in range(len(polygon)):
        x1,y1=polygon[i-1];x2,y2=polygon[i]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:
            hit=not hit
    return hit


def body_relation(body,stop):
    """Independent footprint/stop intersection check for the activity interval."""
    flags=[inside(point,stop) for point in body]
    if all(flags):
        return 'inside'
    if any(flags):
        return 'mixed'

    def turn(a,b,c):
        return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

    def touches(a,b,c,d):
        x,y=turn(a,b,c),turn(a,b,d)
        u,v=turn(c,d,a),turn(c,d,b)
        for p,q,r in ((a,b,c),(a,b,d),(c,d,a),(c,d,b)):
            if turn(p,q,r)==0 and min(p[0],q[0])<=r[0]<=max(p[0],q[0]) and min(p[1],q[1])<=r[1]<=max(p[1],q[1]):
                return True
        return (x>0)!=(y>0) and (u>0)!=(v>0)

    if any(touches(body[i-1],body[i],stop[j-1],stop[j]) for i in range(len(body)) for j in range(len(stop))):
        return 'mixed'
    if any(inside(point,body) for point in stop):
        return 'mixed'
    return 'outside'


def verify(case_id: str,attempt: Path,source: dict,decode: dict,physical: dict,
           pixels: dict,activity: dict,designation: dict,core: dict) -> dict:
    if case_id not in {ASSIGNMENT+'__'+suffix for suffix in SUFFIXES}:
        raise ValueError('unknown exact bus-stop case')
    attempt=attempt.resolve()
    if source.get('case_id')!=case_id or source.get('passed') is not True or source.get('source_kind')!='original_native_capture':
        raise ValueError('original Native source chain unverified')
    if physical.get('case_id')!=case_id or physical.get('provenance_kind')!='native' or physical.get('diagnostic_fixture') is not False:
        raise ValueError('original physical source absent')
    if physical.get('maneuver_completed') is not True:
        raise ValueError('complete bus arrival, stop interval and departure unverified')
    checks=physical.get('physical_checks',{})
    if not {'setup','target','maneuver'}<=set(checks):
        raise ValueError('physical checks incomplete')
    for item in checks.values():
        if item.get('status')!='met' or not item.get('sources'):
            raise ValueError('physical check lacks original sources')
        for relative,digest in item['sources'].items():
            path=(attempt/relative).resolve()
            if not path.is_relative_to(attempt) or not path.is_file() or sha(path)!=digest:
                raise ValueError('physical completion source changed: '+relative)
    frame_map=attempt/'video_frames.jsonl'
    rows=[json.loads(line) for line in frame_map.read_text().splitlines()]
    scenes=core.get('scenes',[])
    if len(rows)!=900 or len(scenes)!=900 or source.get('frames')!=900:
        raise ValueError('900 original bus frames required')
    if source.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('original bus frame map changed')
    for index,(row,scene) in enumerate(zip(rows,scenes)):
        if row.get('video_frame')!=index or scene.get('t')!=round(row.get('time_s',-1)*1000):
            raise ValueError('Core/original bus frame time join differs')
    if decode.get('case_id')!=case_id or decode.get('passed') is not True:
        raise ValueError('full original video decode unverified')
    videos=decode.get('videos',{})
    if set(videos)!=set(VIEWS):
        raise ValueError('four original bus views required')
    for view in VIEWS:
        item=videos[view];path=attempt/(view+'.mkv')
        if item.get('frames')!=900 or item.get('sha256')!=sha(path):
            raise ValueError('decoded bus view source changed: '+view)
    if pixels.get('format')!='worker-original-pixel-review' or pixels.get('case_id')!=case_id or pixels.get('diagnostic_fixture') is not False or not pixels.get('reviewer'):
        raise ValueError('independent original bus pixel review missing')
    if pixels.get('frame_map_sha256')!=sha(frame_map) or pixels.get('video_sha256')!=sha(attempt/'overview.mkv'):
        raise ValueError('original bus pixel source changed')
    for name in ('bus_body','stop_boundary','public_street','designation_signs'):
        item=pixels.get('observations',{}).get(name,{})
        if item.get('visible') is not True or item.get('view') not in VIEWS or not isinstance(item.get('frame'),int) or not 0<=item['frame']<900 or not item.get('description'):
            raise ValueError('actual bus-stop pixels unverified: '+name)
    if designation.get('case_id')!=case_id or designation.get('authority')!='City Traffic Engineer' or not designation.get('reviewer') or designation.get('diagnostic_fixture') is not False:
        raise ValueError('actual official stop designation review missing')
    if designation.get('signed') is not True or designation.get('route_termini_reviewed') is not True or designation.get('other_permitted_locations_reviewed') is not True:
        raise ValueError('other permitted bus locations or signed stop unreviewed')
    if designation.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('designation/original attempt join changed')
    if activity.get('case_id')!=case_id or activity.get('diagnostic_fixture') is not False or not activity.get('reviewer') or activity.get('frame_map_sha256')!=sha(frame_map):
        raise ValueError('independent original bus activity review missing')
    conduct,relation=case_id.split('__')[-1].split('_')
    if activity.get('conduct')!=conduct or activity.get('complete_interval') is not True or activity.get('intervening_loading') is not False:
        raise ValueError('complete standing/parking activity unverified')
    interval=activity.get('interval_frames')
    if not isinstance(interval,list) or len(interval)!=2 or not all(isinstance(x,int) for x in interval) or not 0<=interval[0]<interval[1]<900:
        raise ValueError('original bus activity interval missing')
    site_path=attempt/'site.json';native_path=attempt/'native.json'
    if designation.get('site_sha256')!=sha(site_path) or source.get('native_sha256')!=sha(native_path):
        raise ValueError('reviewed site or original bus ledger changed')
    site=json.loads(site_path.read_text());native=json.loads(native_path.read_text())
    if site.get('public_street') is not True or site.get('cell_id')!='C386411' or site.get('source_class')!='original_independent_review':
        raise ValueError('original one-way public street missing')
    polygon=site.get('stop_polygon_xy_m')
    frames=native.get('frames',[])
    if not isinstance(polygon,list) or len(polygon)<4 or len(frames)!=900:
        raise ValueError('reviewed stop polygon or Native bus history missing')
    observed=[]
    for i in range(interval[0],interval[1]+1):
        row=frames[i];footprint=row.get('bus_footprint_xy_m')
        if row.get('frame')!=i or row.get('time_s')!=i/20 or not isinstance(footprint,list) or len(footprint)!=4:
            raise ValueError('original bus footprint/time join missing')
        location=body_relation(footprint,polygon)
        if location=='mixed':
            raise ValueError('original bus body straddles stop boundary')
        inside_stop=location=='inside'
        if row.get('inside_stop_boundary') is not inside_stop:
            raise ValueError('original stop body measurement changed')
        observed.append(inside_stop)
        if relation=='outside' and row.get('outside_other_permitted_location') is not True:
            raise ValueError('outside stop may be another permitted location')
    if (relation=='inside' and not all(observed)) or (relation=='outside' and any(observed)):
        raise ValueError('original body/stop location differs from selected probe')
    return {'format':'worker-bus-stop-location-delivery-audit','passed':True,'case_id':case_id,
            'checks':{key:True for key in CHECKS},'frames':900,
            'frame_map_sha256':sha(frame_map),'location_relation':relation,
            'conduct':conduct,'legal_verdict':None}

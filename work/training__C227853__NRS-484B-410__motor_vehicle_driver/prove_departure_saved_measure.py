"""Synthetic 600-frame source-shape checks, never a safety or physical finding."""
import copy
import hashlib
import json
from pathlib import Path

from departure_saved_measure import ASSIGNMENT, CAMERAS, measure, measure_original


def enc(obj):
    return json.dumps(obj,sort_keys=True,separators=(',',':')).encode()


def lines(rows):
    return ('\n'.join(json.dumps(x,sort_keys=True) for x in rows)+'\n').encode()


def box(x,y,half_length=2.0,half_width=.8):
    return [[x-half_length,y-half_width],[x+half_length,y-half_width],
            [x+half_length,y+half_width],[x-half_length,y+half_width]]


def sample(conflict=False, permitted=True):
    h=hashlib.sha256(b'synthetic departure source shape only').hexdigest()
    context={'assignment_id':ASSIGNMENT,'source_kind':'synthetic_native_sample',
             'map_source_sha256':h,'highway_boundary_source_sha256':h,
             'highway_dedication_source_sha256':h,'public_access_source_sha256':h,
             'curb_permission_source_sha256':h,'parking_purpose_source_sha256':h,
             'state':'Nevada','public_highway':True,'parking_permitted':permitted,
             'initial_status':'parked_no_loading','road_id':'1'}
    frames=[]
    for i in range(600):
        elapsed=max(0,i-150)
        ex=elapsed*.1
        ey=-5+min(1,elapsed/50)*3.25
        tx=(-50+i*.3) if conflict else (30+i*.25)
        ts=6 if not conflict or i<180 else 3
        frames.append({'video_frame':i,'native_frame':1000+i,'time_s':i/20,
            'camera_native_frames':{name:1000+i for name in CAMERAS},
            'ego_id':'ego','traffic_id':'traffic','ego_road_id':'1','traffic_road_id':'1',
            'ego_footprint_xy_m':box(ex,ey),'traffic_footprint_xy_m':box(tx,-1.75),
            'ego_speed_mps':0 if i<150 else 2,'traffic_speed_mps':ts})
    return {'assignment_id':ASSIGNMENT,'source_kind':'synthetic_native_sample',
            'ego_id':'ego','traffic_id':'traffic','frames':frames},context


def reject(packet,context,message):
    try:
        measure(enc(packet),enc(context))
    except ValueError as exc:
        if str(exc)!=message:
            raise
        return
    raise RuntimeError('invalid departure source accepted: '+message)


def main():
    root=Path(__file__).resolve().parents[2]
    source=root/'inputs'/ASSIGNMENT
    hashes={n:hashlib.sha256((source/n).read_bytes()).hexdigest()
            for n in ('assignment.json','witnesses.json')}
    law=json.loads((source/'assignment.json').read_text())['law']['text']
    if ('unless and until such movement can be made with safety' not in law or
            'except when stopping, standing or parking where no parking is permitted' not in law):
        raise ValueError('frozen law text changed')
    clear,context=sample()
    conflict,context2=sample(conflict=True)
    excepted,context3=sample(permitted=False)
    good=measure(enc(clear),enc(context))
    bad=measure(enc(conflict),enc(context2))
    exception=measure(enc(excepted),enc(context3))
    if (good['ego_start_frame']!=150 or bad['ego_start_frame']!=150 or
            not bad['minimum_surface_gap_during_first_10s_after_start_m'] < good['minimum_surface_gap_during_first_10s_after_start_m'] or
            bad['max_observed_traffic_deceleration_mps2'] <= 0 or
            exception['parking_permitted_source_fact'] is not False or
            any(x['legal_safety_result'] is not None for x in (good,bad,exception))):
        raise RuntimeError('departure diagnostic mismatch')
    failures=[
      ('missing_highway',lambda p,c:c.__setitem__('highway_dedication_source_sha256',''),
       'highway_dedication_source_sha256 missing'),
      ('no_public_access',lambda p,c:c.__setitem__('public_highway',False),
       'Nevada highway source missing'),
      ('unknown_curb',lambda p,c:c.__setitem__('parking_permitted',None),
       'curb parking permission unresolved'),
      ('unknown_purpose',lambda p,c:c.__setitem__('initial_status','unknown'),
       'initial parked purpose unresolved'),
      ('changed_traffic',lambda p,c:p['frames'][300].__setitem__('traffic_id','other'),
       'participant identity changed'),
      ('missing_camera',lambda p,c:p['frames'][300]['camera_native_frames'].pop('approach'),
       'four-camera frame join missing'),
      ('missing_frame',lambda p,c:p['frames'].pop(300),
       'recording shorter than 30 seconds'),
      ('no_initial_rest',lambda p,c:p['frames'][50].__setitem__('ego_speed_mps',2),
       'initial stationary history missing'),
      ('no_departure',lambda p,c:[r.__setitem__('ego_speed_mps',0) for r in p['frames']],
       'vehicle never starts'),
    ]
    for _,change,message in failures:
        p,c=copy.deepcopy(clear),copy.deepcopy(context)
        change(p,c)
        reject(p,c,message)
    road=b'<OpenDRIVE diagnostic="synthetic-shape-only" />'
    context['source_kind']='native_saved_sample'
    context['map_source_sha256']=hashlib.sha256(road).hexdigest()
    traces=lines(clear['frames'])
    maps=lines([{'video_frame':r['video_frame'],'native_frame':r['native_frame'],
                 'time_s':r['time_s'],'camera_native_frames':r['camera_native_frames']}
                for r in clear['frames']])
    joined=measure_original(traces,maps,enc(context),road)
    if joined['ego_start_frame']!=150:
        raise RuntimeError('original frame join failed')
    try:
        measure_original(traces,maps,enc(context),b'changed map')
    except ValueError as exc:
        if str(exc)!='OpenDRIVE source hash mismatch':
            raise
    else:
        raise RuntimeError('changed map accepted')
    print(json.dumps({'passed':True,'frozen_source_hashes':hashes,
        'clear_trace_sha256':good['trace_sha256'],'conflict_trace_sha256':bad['trace_sha256'],
        'exception_trace_sha256':exception['trace_sha256'],
        'negative_checks':[n for n,_,_ in failures]+['changed_opendrive'],
        'original_trace_sha256':joined['original_trace_sha256'],
        'physical_acceptance_claimed':False},sort_keys=True))


if __name__=='__main__':
    main()

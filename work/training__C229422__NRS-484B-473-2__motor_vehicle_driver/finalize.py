"""Saved-only optical lamp measurement from original Native sources.

The original camera streams and independent reviewed findings are immutable.
No Native lamp request or nighttime weather setting becomes a legal finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from controller import CASE_MODES, FRAMES
from lamp_source_measure import CAMERAS, measure_files


def require(ok,message):
    if not ok:raise ValueError(message)


def source(root,name):
    path=root/name
    require(path.is_file(),'Missing required source: '+name)
    return path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def video_info(path):
    p=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames,width,height','-of','json',str(path)],
        capture_output=True,text=True,timeout=120)
    require(p.returncode==0,'Original camera decode failed: '+path.name)
    streams=json.loads(p.stdout).get('streams',[])
    require(len(streams)==1 and str(streams[0].get('nb_read_frames','')).isdigit(),
            'Original camera frames missing: '+path.name)
    return streams[0]


def measure_lamp_interval(measured):
    return {'activation':measured['activation'],
            'optical_frame_counts':measured['optical_frame_counts'],
            'legal_conclusion':None}


def measure_exception_context(measured):
    return {'cowl_or_parking_used_frames':measured['optical_frame_counts']['cowl_or_parking'],
            'headlamp_dimming_duty_applies':None,
            'legal_conclusion':None}


def finalize(attempt,output):
    root=Path(attempt).resolve();output=Path(output).resolve()
    require(not output.exists() and not (root/'result.json').exists(),
            'Fresh saved-only original attempt required')
    config=json.loads(source(root,'config.json').read_text())
    case=config.get('case_id','');prefix='training__C229422__NRS-484B-473-2__motor_vehicle_driver__'
    require(case.startswith(prefix) and case[len(prefix):] in CASE_MODES and
            config.get('mode')==CASE_MODES[case[len(prefix):]] and
            config.get('duration_frames')==FRAMES,'Selected exact lamp case differs')
    camera_hashes={}
    for name,camera in zip(CAMERAS,config['cameras']):
        path=source(root,name+'.mkv');info=video_info(path)
        require(name==camera['name'] and int(info['nb_read_frames'])==FRAMES and
                info['width']==camera['width'] and info['height']==camera['height'],
                'Original four-camera dimensions or duration differ: '+name)
        camera_hashes[name]=digest(path)
    review=json.loads(source(root,'lamp-pixel-review.json').read_text())
    scene_raw=source(root,'original-scene-review.json').read_bytes()
    require(review.get('scene_sha256')==hashlib.sha256(scene_raw).hexdigest(),
            'Optical review does not bind original scene')
    scene=json.loads(scene_raw)
    require(scene.get('case_id')==case,'Original scene binds another case')
    for label in ('highway','parking_rule','civil_clock','sunset_sunrise'):
        original=source(root,'original-'+label+'.json')
        require(scene.get('sources',{}).get(label,{}).get('sha256')==digest(original),
                'Original cited source changed: '+label)
    if rows(source(root,'parked-lamp-trace.jsonl'))[0].get('source_kind')=='original_native_observation':
        require(review.get('source_kind')=='independent_original_review',
                'Original Native capture needs independent optical review')
    measured=measure_files(root)
    require(measured['camera_sha256']==camera_hashes,
            'Original camera source hashes changed')
    counts=measured['optical_frame_counts'];trace=rows(source(root,'parked-lamp-trace.jsonl'))
    mapping=rows(source(root,'video_frames.jsonl'))
    observed=review['optical_observations']
    source(root,'trace.jsonl')
    names=[c['name'] for c in config['recording_description']['channels']]
    required=('kin.time','drv.standing_or_parked','sig.headlamp','sig.position_lamp',
              'drv.civil_night','env.darkness','st.highway','env.civil_time')
    require(tuple(names)==required,'Parked lamp recording description differs')
    channels=root/'channels';channels.mkdir(exist_ok=True)
    values={
        'kin.time':lambda i:mapping[i]['native_elapsed_s'],
        'drv.standing_or_parked':lambda i:{'stopped':trace[i]['ego_speed_mps']<=0.1,
            'lawfully_parked_reviewed':measured['activation']['lawfully_parked']},
        'sig.headlamp':lambda i:{'displayed':observed[i]['lights_displayed'],
            'depressed_or_dimmed':observed[i]['depressed_or_dimmed'],
            'undepressed':observed[i]['undepressed_headlamp'],
            'original_pixel_source':'lamp-pixel-review.json#'+str(i)},
        'sig.position_lamp':lambda i:{'cowl_or_parking_used':observed[i]['cowl_or_parking_used'],
            'original_pixel_source':'lamp-pixel-review.json#'+str(i)},
        'drv.civil_night':lambda i:{'reviewed':measured['activation']['civil_night'],
            'source':'original-civil_clock.json'},
        'env.darkness':lambda i:{'source':'lamp-pixel-review.json#'+str(i),
            'nighttime_not_inferred_from_darkness':True},
        'st.highway':lambda i:{'reviewed':measured['activation']['highway'],
            'road_id':trace[i]['road_id'],'source':'original-highway.json'},
        'env.civil_time':lambda i:{'source':'original-civil_clock.json',
            'elapsed_s':i/20}}
    evidence=[]
    for name in names:
        path=channels/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s':i/20,'value':values[name](i)},
            allow_nan=False)+'\n' for i in range(FRAMES)))
        evidence.append({'name':name,'unit':'structured','reference':'channels/'+name+'.jsonl'})
    context_folder=root/'contexts';context_folder.mkdir(exist_ok=True)
    for item in config['recording_description']['context_inputs']:
        name=item['name']
        original=source(root,name)
        reference='contexts/'+name
        (root/reference).write_text(json.dumps({name:{'source_sha256':digest(original),
            'source_kind':'original_acquisition_or_cited_review'}},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':item['unit'],'reference':reference})
    from worker_exchange.native_output import write_result
    result={'case_id':case,'measured_values':measured,
        'target_checks':[{'target':'full-interval original optical lamp state',
            'requested':config['mode'],'measured':counts,'method':'independent source pixels',
            'tolerance':None,'matched':None,'physical_cause_confirmed':False,
            'cause_evidence':['lamp-pixel-review.json','parked-lamp-trace.jsonl']}],
        'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
        'termination_reason':'Saved original interval measured; lawful parking and legal result separately reviewed',
        'physical_failure_flags':['original_physical_completion_review_required'],
        'trace_reference':'trace.jsonl','video_references':[name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],'recording_evidence':evidence,
        'realized_observables':{'displayed_lamp_frames':{'value':counts['displayed'],
            'unit':'frames','statistic':'count','method':'reviewed original pixels',
            'time_window':'600 original frames','sample_window_s':[0,599/20],
            'reference':'channels/sig.headlamp.jsonl'}},
        'legal_verdict_claimed':False,'physical_acceptance_claimed':False}
    write_result(root,result)
    source_hashes={name:digest(source(root,name)) for name in
        ('parked-lamp-trace.jsonl','video_frames.jsonl','lamp-pixel-review.json',
         'original-scene-review.json','original-highway.json','original-parking_rule.json',
         'original-civil_clock.json','original-sunset_sunrise.json')}
    report={'format':'c229422-lamp-saved-analysis-v1','case_id':case,
        'measurements':{
            'lamp_interval':{'value':measure_lamp_interval(measured),
                'method':'measure_lamp_interval','sources':source_hashes},
            'exception_context':{'value':measure_exception_context(measured),
                'method':'measure_exception_context','sources':source_hashes}},
        'measured':measured,'camera_sha256':camera_hashes,
        'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    print(json.dumps({'case_id':finalize(a.attempt,a.output)['case_id'],'passed':True}))

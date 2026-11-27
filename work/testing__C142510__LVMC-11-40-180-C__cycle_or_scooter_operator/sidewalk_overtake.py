"""Source-bound sidewalk overtake and original audible-waveform observations.

A detected waveform is an engineering source observation, not a legal audibility
or right-of-way finding. A trail label alone does not establish a sidewalk.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import wave
from pathlib import Path

ASSIGNMENT='testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator'
SOURCES=('road.xodr','site-context.json','rider-body-history.jsonl',
         'pedestrian-body-history.jsonl','emitter-event-history.jsonl',
         'pedestrian-microphone.wav')


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(x):return type(x) in (int,float) and math.isfinite(x)


def source(root,manifest,name):
    path=root/name;binding=manifest.get(name)
    need(path.is_file() and not path.is_symlink() and isinstance(binding,dict)
         and binding.get('kind')=='original_native' and binding.get('sha256')==sha(path),
         'missing or stale original source: '+name)
    return path


def polygon(value):
    need(isinstance(value,list) and len(value)>=3 and
         all(isinstance(p,list) and len(p)==2 and all(number(v) for v in p)
             for p in value),'invalid original sidewalk/body polygon')
    points=[(float(x),float(y)) for x,y in value]
    signs=[]
    for i in range(len(points)):
        a,b,c=(points[(i+j)%len(points)] for j in range(3))
        cross=(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-a[0])
        need(abs(cross)>1e-9,'degenerate sidewalk/body polygon')
        signs.append(cross>0)
    need(all(s==signs[0] for s in signs),'nonconvex sidewalk/body polygon')
    return points


def contains(region,body):
    sign=None
    for i,a in enumerate(region):
        b=region[(i+1)%len(region)]
        for p in body:
            cross=(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
            if abs(cross)<1e-9:continue
            value=cross>0
            if sign is None:sign=value
            elif sign!=value:return False
    return True


def rows(path):
    lines=path.read_text(encoding='utf-8').splitlines()
    need(len(lines)>=3 and all(line.strip() for line in lines),
         'complete original body history required: '+path.name)
    return [json.loads(line) for line in lines]


def audio_onset(path,site):
    with wave.open(str(path),'rb') as stream:
        need(stream.getnchannels()==1 and stream.getsampwidth()==2,
             'original microphone must be mono PCM16')
        rate=stream.getframerate();frames=stream.getnframes()
        need(rate==site.get('microphone_sample_rate_hz') and rate>=1000,
             'original microphone sample rate differs')
        raw=stream.readframes(frames)
    need(len(raw)==frames*2 and frames>=rate//2,'original microphone waveform incomplete')
    need(number(site.get('microphone_start_time_s')) and
         number(site.get('signal_rms_detection_threshold')) and
         0<site['signal_rms_detection_threshold']<1,
         'microphone clock or engineering detection threshold missing')
    samples=struct.unpack('<'+'h'*frames,raw)
    window=round(rate*.05)
    onset=None;peak=0.0
    for index in range(0,frames-window+1,window):
        rms=math.sqrt(sum((v/32768)**2 for v in samples[index:index+window])/window)
        peak=max(peak,rms)
        if onset is None and rms>=site['signal_rms_detection_threshold']:
            onset=site['microphone_start_time_s']+index/rate
    return {'onset_time_s':onset,'peak_window_rms':peak,'sample_rate_hz':rate,
            'sample_count':frames,'detection_threshold':site['signal_rms_detection_threshold']}


def measure(attempt):
    root=Path(attempt)
    need(root.is_dir() and not root.is_symlink(),'saved attempt directory missing')
    manifest_path=root/'source-manifest.json'
    need(manifest_path.is_file() and not manifest_path.is_symlink(),
         'original source manifest missing')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    files={name:source(root,manifest,name) for name in SOURCES}
    site=json.loads(files['site-context.json'].read_text(encoding='utf-8'))
    need(site.get('assignment_id')==ASSIGNMENT and site.get('cell_id')=='C142510',
         'wrong saved assignment/cell')
    need(site.get('map_sha256')==sha(files['road.xodr']) and
         site.get('sidewalk_map_sha256')==sha(files['road.xodr']),
         'original map differs from reviewed sidewalk source')
    for key in ('reviewer','sidewalk_source_citation','sidewalk_id',
                'connected_route_citation','microphone_calibration_source'):
        need(isinstance(site.get(key),str) and site[key],
             'reviewed sidewalk/audio source missing: '+key)
    need(site.get('physical_surface_kind')=='sidewalk' and
         site.get('sidewalk_connected') is True,
         'physical connected sidewalk not established')
    need(site.get('rider_kind') in ('bicycle','electric_bicycle','electric_scooter'),
         'covered rider kind missing')
    need(type(site.get('rider_actor_id')) is int and
         type(site.get('pedestrian_actor_id')) is int and
         site['rider_actor_id']!=site['pedestrian_actor_id'],
         'distinct original rider/pedestrian identities required')
    need(type(site.get('emitter_actor_id')) is int and
         site['emitter_actor_id'] not in (site['rider_actor_id'],site['pedestrian_actor_id']) and
         number(site.get('microphone_propagation_max_s')) and
         0<=site['microphone_propagation_max_s']<=.2,
         'source-bound emitter identity or propagation window missing')
    direction=site.get('sidewalk_travel_unit_xy')
    need(isinstance(direction,list) and len(direction)==2 and
         all(number(x) for x in direction) and
         abs(math.hypot(*direction)-1)<1e-6,'reviewed sidewalk direction missing')
    region=polygon(site.get('sidewalk_polygon_xy_m'))
    rider=rows(files['rider-body-history.jsonl'])
    pedestrian=rows(files['pedestrian-body-history.jsonl'])
    emitter=rows(files['emitter-event-history.jsonl'])
    need(len(rider)==len(pedestrian)==len(emitter),'original actor/emitter histories unequal')
    previous=None;relative=[];separations=[];brake_frames=[];approach_speeds=[]
    emitted=[]
    for a,b,e in zip(rider,pedestrian,emitter):
        frame,time=a.get('frame'),a.get('time_s')
        need((frame,time)==(b.get('frame'),b.get('time_s')),
             'original rider/pedestrian frame/time join differs')
        need(a.get('actor_id')==site['rider_actor_id'] and
             b.get('actor_id')==site['pedestrian_actor_id'],
             'original actor identity differs')
        need(e.get('frame')==frame and e.get('time_s')==time and
             e.get('actor_id')==site['emitter_actor_id'] and
             e.get('source')=='original_native' and
             type(e.get('emitted')) is bool,
             'original audible emitter event/frame join differs')
        if e['emitted']:emitted.append(time)
        need(type(frame) is int and number(time),'original frame/time missing')
        if previous:
            need(frame==previous[0]+1 and .049<=time-previous[1]<=.051,
                 'original 20 Hz frame sequence differs')
        previous=frame,time
        need(number(a.get('rider_speed_mps')) and a['rider_speed_mps']>=0 and
             type(a.get('rider_brake_applied')) is bool,
             'original rider speed or brake source missing')
        pa,pb=polygon(a.get('body_vertices_xy_m')),polygon(b.get('body_vertices_xy_m'))
        need(contains(region,pa) and contains(region,pb),
             'original participants leave reviewed sidewalk polygon')
        ca=(sum(p[0] for p in pa)/len(pa),sum(p[1] for p in pa)/len(pa))
        cb=(sum(p[0] for p in pb)/len(pb),sum(p[1] for p in pb)/len(pb))
        relative.append((frame,time,(ca[0]-cb[0])*direction[0]+(ca[1]-cb[1])*direction[1]))
        separations.append(math.dist(ca,cb))
        approach_speeds.append(a['rider_speed_mps'])
        if a['rider_brake_applied']:brake_frames.append(frame)
    need(relative[0][2]<0,'rider is not behind pedestrian in original approach')
    pass_index=next((i for i in range(1,len(relative)) if relative[i-1][2]<=0<relative[i][2]),None)
    need(pass_index is not None,'original rider did not overtake and pass pedestrian')
    audio=audio_onset(files['pedestrian-microphone.wav'],site)
    need(site['microphone_start_time_s']<=relative[0][1] and
         site['microphone_start_time_s']+audio['sample_count']/audio['sample_rate_hz']>=relative[-1][1],
         'original microphone does not cover complete rider/pedestrian episode')
    if audio['onset_time_s'] is not None:
        need(any(0<=audio['onset_time_s']-event<=site['microphone_propagation_max_s']
                 for event in emitted),
             'microphone onset has no source-bound emitter event')
    before=audio['onset_time_s'] is not None and audio['onset_time_s']<relative[pass_index][1]
    return {'format':'worker-c142510-sidewalk-overtake-v1','assignment_id':ASSIGNMENT,
            'case_id':site.get('case_id'),'sidewalk_id':site['sidewalk_id'],
            'rider_kind':site['rider_kind'],'pass_frame':relative[pass_index][0],
            'pass_time_s':relative[pass_index][1],
            'pass_bracket_s':[relative[pass_index-1][1],relative[pass_index][1]],
            'minimum_center_separation_m':min(separations),
            'minimum_approach_speed_mps':min(approach_speeds[:pass_index+1]),
            'brake_frames_before_pass':[f for f in brake_frames if f<relative[pass_index][0]],
            'microphone':audio,'original_emitter_event_times_s':emitted,
            'detected_signal_before_pass':before,
            'frame_count':len(rider),
            'source_sha256':{name:manifest[name]['sha256'] for name in SOURCES},
            'yielding_right_of_way':'unresolved_original_behavior_review',
            'audible_to_pedestrian':'unresolved_physical_and_legal_review',
            'legal_verdict_claimed':False}


def compare(left,right,variable='signal_timing'):
    need(all(x.get('format')=='worker-c142510-sidewalk-overtake-v1' and
             x.get('assignment_id')==ASSIGNMENT and x.get('source_sha256')
             for x in (left,right)),'source-bound exact measurements required')
    need(left.get('case_id')!=right.get('case_id') and
         all(x.get('case_id') for x in (left,right)),
         'two distinct exact cases required')
    for field in ('sidewalk_id','rider_kind','frame_count'):
        need(left.get(field)==right.get(field),'fixed comparison condition changed: '+field)
    need(variable in ('signal_timing','rider_response'),'unsupported comparison variable')
    if variable=='signal_timing':
        need(left.get('detected_signal_before_pass')!=right.get('detected_signal_before_pass'),
             'declared signal-timing difference not measured')
        need(left.get('brake_frames_before_pass')==right.get('brake_frames_before_pass'),
             'fixed rider response changed')
    else:
        need(left.get('detected_signal_before_pass')==right.get('detected_signal_before_pass'),
             'fixed signal timing changed')
        need(bool(left.get('brake_frames_before_pass'))!=bool(right.get('brake_frames_before_pass')),
             'declared rider-response difference not measured')
    return {'format':'worker-c142510-comparison-audit-v1',
            'case_ids':[left['case_id'],right['case_id']],
            'declared_difference':variable,
            'legal_verdict_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=measure(args.attempt)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n',encoding='utf-8')


if __name__=='__main__':main()

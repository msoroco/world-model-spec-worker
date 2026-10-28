"""Saved-only source joins and capability measurements for partition-04 experiments."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(s) for s in Path(path).read_text().splitlines() if s.strip()]


def analyze(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt/'config.json').read_text())
    case = config['case']
    mode = config['mode']
    trace = rows(attempt/'trace.jsonl')
    evidence = rows(attempt/'capture/evidence.jsonl')
    mapping = rows(attempt/'video_frames.jsonl')
    names = [c['name'] for c in case['recording_description']['channels']]
    channels = {name: rows(attempt/'channels'/(name+'.jsonl')) for name in names}
    if not trace or len({len(trace),len(evidence),len(mapping),*(len(v) for v in channels.values())}) != 1:
        raise ValueError('Original source counts differ')
    for i,(point,event,frame) in enumerate(zip(trace,evidence,mapping)):
        if point['frame']!=event['original_frame'] or point['frame']!=frame.get('carla_frame') or frame.get('native_frame')!=point['frame'] or frame.get('video_frame')!=i:
            raise ValueError('Original frame identity differs')
        for name,values in channels.items():
            if values[i].get('value') is None or abs(values[i]['time_s']-point['time_s'])>1e-6:
                raise ValueError('Original channel value/time differs: '+name)
    fixture = (attempt/'fixture-provenance.json').is_file()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv'%i for i in range(4)]
    mapping_sha = hashlib.sha256((attempt/'video_frames.jsonl').read_bytes()).hexdigest()
    decoded = {}
    for i,video in enumerate(videos):
        receipt = audit(attempt/video,len(trace),mapping_sha256=mapping_sha,receipt=attempt/('source-%d.json'%i))
        if not fixture and receipt['dimensions'] != ([1920,1080] if i==0 else [1280,720]):
            raise ValueError('Source camera dimensions differ')
        decoded[video]=receipt['frames']
    speed=[r['speed_mps'] for r in trace]
    pos=[r['position'] for r in trace]
    obs=[r['value'] for r in channels['source_observations']]
    other=[v.get('other') for v in obs]
    dt=(trace[-1]['time_s']-trace[0]['time_s'])/(len(trace)-1) if len(trace)>1 else .05
    measurements={'original_frames':len(trace),'max_speed_mps':max(speed),
                  'first_time_s':trace[0]['time_s'],'last_time_s':trace[-1]['time_s']}
    checks=[]
    if mode=='winter_follow':
        following_rows=[(v,p,row,i) for i,(v,p,row) in enumerate(zip(other,pos,obs))
                        if v and p['x']<15 and abs(p['y']-v['position_m'][1])<2.5]
        gaps=[v['position_m'][0]-p['x'] for v,p,row,i in following_rows]
        body_gaps=[]
        for v,p,row,i in following_rows:
            if v.get('body_vertices_m') and row.get('ego_body_vertices_m'):
                body_gaps.append(min(p[0] for p in v['body_vertices_m'])-max(p[0] for p in row['ego_body_vertices_m']))
        hard_decel=sum((speed[i-1]-speed[i])/dt >= 3 for i in range(1,len(speed)))
        time_gaps=[gap/max(speed[i],.1) for gap,(_,_,_,i) in zip(gaps,following_rows) if speed[i]>.1]
        lead_speeds=[v['speed_mps'] for v,_,_,_ in following_rows]
        lane_change_started=any(p['x']>=15 and p['y']<-2. for p in pos)
        lane_change_completed=bool(pos[-1]['y']<-5. and not fixture)
        measured=sum(gaps)/len(gaps) if gaps else None
        measurements.update(mean_centre_gap_m=measured,minimum_body_gap_m=min(body_gaps) if body_gaps else None,
                            gap_samples=len(gaps),minimum_time_gap_s=min(time_gaps) if time_gaps else None,
                            lead_speed_samples_mps=lead_speeds,following_interval_end_x_m=15.,
                            lane_change_started=lane_change_started,lane_change_completed=lane_change_completed,
                            hard_deceleration_samples=hard_decel,
                            weather_surface_commanded=case['variable_assignments']['weather_surface']['value'],
                            native_ice_or_snow_observed=False)
        checks.append({'target':'commanded_gap_m','requested':case['variable_assignments']['commanded_gap_m']['value'],
                       'measured':measured if measured is not None else 0.,'matched':measured is not None and abs(measured-case['variable_assignments']['commanded_gap_m']['value'])<=3,
                       'physical_cause_confirmed':False,'cause_evidence':'source_observations and trace'})
    elif mode=='signed_speed':
        controls_path=attempt/'native-controls.json'
        if not controls_path.is_file(): raise ValueError('Native control inventory missing')
        controls=json.loads(controls_path.read_text())
        signs=[v for v in controls.get('landmarks',[]) if str(v.get('type')) in ('274','274.1','speed_limit','SpeedLimit')]
        measurements.update(native_speed_sign_metadata=signs,signed_zone_observed=bool(signs) and not fixture,
                            sign_rendering_verified=False)
        requested=case['variable_assignments']['target_speed_mps']['value']
        checks.append({'target':'target_speed_mps','requested':requested,'measured':max(speed),
                       'matched':abs(max(speed)-requested)<=2,'physical_cause_confirmed':False,'cause_evidence':'trace; native-controls'})
    elif mode in ('signal_amber','signal_dark'):
        controls_path=attempt/'native-controls.json'
        if not controls_path.is_file(): raise ValueError('Native control inventory missing')
        controls=json.loads(controls_path.read_text())
        states=[v.get('traffic_light_states') for v in obs if v.get('traffic_light_states')]
        stopped=sum(s<.05 and p['x']<-10 for s,p in zip(speed,pos))*dt
        entered=next((trace[i]['time_s'] for i,p in enumerate(pos) if p['x']>=-7),None)
        counterpart=next((trace[i]['time_s'] for i,v in enumerate(other) if v and v['position_m'][0]<=7),None)
        measurements.update(native_signal_landmarks=controls.get('landmarks',[]),native_signal_actors=controls.get('traffic_light_actors',[]),
                            signal_state_samples=states,pre_entry_stationary_s=stopped,
                            ego_entry_time_s=entered,counterpart_entry_time_s=counterpart,
                            original_inoperative_signal_verified=False,
                            original_yellow_transition_verified=any(any('Yellow' in str(z.get('state')) for z in state) for state in states))
        requested=case['variable_assignments']['stop_duration_s']['value']
        checks.append({'target':'stop_duration_s','requested':requested,'measured':stopped,
                       'matched':abs(stopped-requested)<=.2,'physical_cause_confirmed':False,'cause_evidence':'trace; source_observations'})
    else: raise ValueError('Unknown mode')
    for check in checks:
        check.setdefault('method','original source telemetry and same-frame native observation')
        check.setdefault('tolerance',3. if mode=='winter_follow' else (2. if mode=='signed_speed' else .2))
    route_end=not fixture and obs[-1].get('route_index') is not None and obs[-1]['route_index']>=config['route_last_index']-2
    report={'format':'partition04-capability-report-v1','case_id':case['case_id'],'mode':mode,
            'measurements':measurements,'decoded_sources':decoded,'original_join':True,'physical_acceptance':False,
            'decision':'inspect_original_native_evidence' if route_end else 'repair_same_frozen_case',
            'follow_up':{'same_case_id':case['case_id'],'preserve_targets':True,'requires_new_attempt':not route_end},
            'unresolved':['native legal setting and device authority','physical movement and weather outcome','camera visibility']}
    native={'case_id':case['case_id'],'measured_values':measurements,'target_checks':checks,
            'setup_confirmed':False,'behavior_attempted':not fixture and len(trace)>1,'maneuver_completed':bool(route_end),
            'termination_reason':'diagnostic subset without maneuver' if fixture else ('measured route endpoint' if route_end else 'incomplete original route'),
            'physical_failure_flags':{'setup_unconfirmed':True,'visibility_unverified':True},
            'trace_reference':'trace.jsonl','video_references':videos,'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':case['recording_description'],
            'recording_evidence':[{'name':c['name'],'unit':c['unit'],'reference':'channels/'+c['name']+'.jsonl'} for c in case['recording_description']['channels']],
            'realized_observables':{}}
    return report,native

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();report,native=analyze(a.attempt);write_result(a.attempt,native)
    Path(a.output).write_text(json.dumps(report,indent=2)+'\n')

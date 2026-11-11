"""Saved-only finalizer for the C136014 original reverse and traffic sources."""
from __future__ import annotations
import argparse
from hashlib import sha256
import json
from math import hypot
from pathlib import Path


def required(root,name):
    p=Path(root)/name
    if not p.is_file():raise ValueError('Missing required source: '+name)
    raw=p.read_bytes()
    if not raw:raise ValueError('Empty required source: '+name)
    return p,sha256(raw).hexdigest()

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def measure_reverse_encounter(root):
    root=Path(root)
    fm,fh=required(root,'video_frames.jsonl');trace,th=required(root,'trace.jsonl')
    backing,bh=required(root,'backing_history.jsonl')
    maps,traces,states=rows(fm),rows(trace),rows(backing)
    if not maps or len(maps)!=len(traces) or len(maps)!=len(states):
        raise ValueError('Original frame-map, trace and backing history length differs')
    previous=None;observed=[]
    for index,(mapped,t,s) in enumerate(zip(maps,traces,states)):
        frame,time=mapped.get('carla_frame'),mapped.get('time_s')
        if (mapped.get('video_frame')!=index or t.get('frame')!=frame or t.get('time_s')!=time
                or s.get('frame')!=frame or s.get('time_s')!=time or type(frame) is not int):
            raise ValueError('Original backing source/frame-map join failed')
        if previous is not None and (frame<=previous[0] or time<=previous[1]):
            raise ValueError('Original frame identities do not increase')
        previous=(frame,time)
        ego,other=s.get('ego',{}),s.get('other',{})
        if s.get('ego_reverse_gear') is not True or not ego.get('actor_id') or not other.get('actor_id'):
            raise ValueError('Reverse gear or participant identity readback absent')
        if ego['actor_id']==other['actor_id'] or not s.get('road_id') or not 2.3<=s.get('lane_width_m',0)<=3.0:
            raise ValueError('Narrow-road participant context differs')
        p,q=ego.get('position_m'),other.get('position_m')
        if not isinstance(p,list) or not isinstance(q,list) or len(p)!=3 or len(q)!=3:
            raise ValueError('Original actor position missing')
        if not isinstance(ego.get('body_vertices_m'),list) or len(ego['body_vertices_m'])!=8 or not isinstance(other.get('body_vertices_m'),list) or len(other['body_vertices_m'])!=8:
            raise ValueError('Original full body footprints missing')
        observed.append({'frame':frame,'time_s':time,'ego_position_m':p,
                         'other_position_m':q,'center_distance_m':hypot(p[0]-q[0],p[1]-q[1]),
                         'ego_speed_mps':ego.get('speed_mps'),'other_speed_mps':other.get('speed_mps')})
    if len(observed)<3 or observed[-1]['ego_position_m'][0]>=observed[0]['ego_position_m'][0]:
        raise ValueError('Original reverse displacement absent')
    return {'reverse_displacement_m':observed[0]['ego_position_m'][0]-observed[-1]['ego_position_m'][0],
            'min_center_distance_m':min(x['center_distance_m'] for x in observed),
            'other_speed_change_mps':observed[-1]['other_speed_mps']-observed[0]['other_speed_mps'],
            'observations':observed}, {'video_frames.jsonl':fh,'trace.jsonl':th,'backing_history.jsonl':bh}

def analyze(root):
    root=Path(root)
    config=json.loads(required(root,'config.json')[0].read_text())
    if config.get('law_id')!='NRS-484B-113-1' or not config.get('selected_case_id','').endswith('__reverse_clear_traffic_steady'):
        raise ValueError('Wrong selected backing case')
    observed,sources=measure_reverse_encounter(root)
    # Derived from retained original state; never an acquisition source.
    (root/'reverse_displacement_m.jsonl').write_text(''.join(json.dumps({'frame':x['frame'],'time_s':x['time_s'],
        'value':observed['observations'][0]['ego_position_m'][0]-x['ego_position_m'][0]})+'\n' for x in observed['observations']))
    (root/'other_traffic_center_distance_m.jsonl').write_text(''.join(json.dumps({'frame':x['frame'],'time_s':x['time_s'],
        'value':x['center_distance_m']})+'\n' for x in observed['observations']))
    return {'format':'worker-analysis-report','case_id':config['selected_case_id'],
            'measurements':{'reverse_encounter':{'method':'measure_reverse_encounter','value':observed,'sources':sources}},
            'legal_acceptance_claimed':False,'physical_acceptance_claimed':False}

def result(root,report):
    root=Path(root);cfg=json.loads((root/'config.json').read_text());obs=report['measurements']['reverse_encounter']['value']
    return {'case_id':report['case_id'],'measured_values':{'reverse_encounter':obs},
            'target_checks':[{'target':'reverse encounter observed','requested':True,
                 'measured':obs['reverse_displacement_m'],'method':'original 20 Hz position displacement',
                 'tolerance':None,'matched':False,'physical_cause_confirmed':False,
                 'cause_evidence':'Original source movement; reasonable safety and interference unverified'}],
            'setup_confirmed':False,'behavior_attempted':obs['reverse_displacement_m']>0,
            'maneuver_completed':False,'termination_reason':'Saved source measurement complete; physical outcome unverified',
            'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
            'recording_evidence':[{'name':'reverse_displacement_m','unit':'m','reference':'reverse_displacement_m.jsonl',
                                   'sha256':sha256((root/'reverse_displacement_m.jsonl').read_bytes()).hexdigest()},
                                  {'name':'other_traffic_center_distance_m','unit':'m','reference':'other_traffic_center_distance_m.jsonl',
                                   'sha256':sha256((root/'other_traffic_center_distance_m.jsonl').read_bytes()).hexdigest()}],
            'realized_observables':{'reverse_displacement_m':{'unit':'m','method':'original ego position displacement',
                  'time_window':'all original frames','statistic':'final','reference':'reverse_displacement_m.jsonl',
                  'value':obs['reverse_displacement_m'],'sample_window_s':[obs['observations'][0]['time_s'],obs['observations'][-1]['time_s']]},
                                    'other_traffic_center_distance_m':{'unit':'m','method':'original actor-center separation',
                  'time_window':'all original frames','statistic':'min','reference':'other_traffic_center_distance_m.jsonl',
                  'value':obs['min_center_distance_m'],'sample_window_s':[obs['observations'][0]['time_s'],obs['observations'][-1]['time_s']]}},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=analyze(a.attempt);out=Path(a.output)
    if out.exists():raise ValueError('Retain prior analysis report')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(a.attempt,result(a.attempt,report))
if __name__=='__main__':main()

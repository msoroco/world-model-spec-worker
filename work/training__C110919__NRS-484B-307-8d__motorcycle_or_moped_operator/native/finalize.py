"""Saved-only right-turn analysis; no statutory or accepted-recording verdict."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

def sha(path: Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path: Path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def source(attempt: Path,name: str):
    path=attempt/name
    if not path.is_file():raise ValueError('Missing required source: '+name)
    return path

def joins(attempt: Path,count: int):
    trace=rows(source(attempt,'trace.jsonl'))
    evidence=rows(source(attempt,'capture/evidence.jsonl'))
    mapping=rows(source(attempt,'video_frames.jsonl'))
    native=rows(source(attempt,'native_samples.jsonl'))
    body=rows(source(attempt,'body_history.jsonl'))
    if any(len(group)!=count for group in (trace,evidence,mapping,native,body)):
        raise ValueError('Saved source frame counts differ')
    previous=-math.inf
    for index,(t,e,m,n,b) in enumerate(zip(trace,evidence,mapping,native,body)):
        frame=m.get('native_frame');time=m.get('time_s')
        if type(frame) is not int or type(time) not in (int,float) or not math.isfinite(time):
            raise ValueError('Invalid original frame or time')
        if m.get('video_frame')!=index or frame<=previous:
            raise ValueError('Original video/Native frame mapping differs')
        previous=frame
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),n.get('native_frame'),b.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(item-time)>1e-4 for item in (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in n['native_body_xy_m']}
        history={(round(v[0],5),round(v[1],5)) for v in b['body_vertices_m']}
        if captured!=measured or measured!=history or len(measured)!=4:
            raise ValueError('Original full body differs')
    manifest=json.loads(source(attempt,'capture/manifest.json').read_text())
    if not manifest.get('extraction_confirmed') or manifest.get('frames')!=count:
        raise ValueError('Capture extraction incomplete')
    return native,mapping,{'frames':count,'first_frame':mapping[0]['native_frame'],
                           'last_frame':mapping[-1]['native_frame'],
                           'source_hashes':{name:sha(source(attempt,name)) for name in
                             ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
                              'native_samples.jsonl','body_history.jsonl','capture/manifest.json')}}

def measure_signal(attempt: Path,native: list[dict],geometry: dict):
    states=[sample.get('signal_state_observed') for sample in native]
    if not states or any(state not in ('Red','TrafficLightState.Red','steady_red') for state in states):
        raise ValueError('Original governing steady red state absent')
    if not geometry.get('signal_actor_id') or geometry.get('stop_line_y_m')!=-14.0:
        raise ValueError('Original signal/stop condition_a readback absent')
    return {'value':{'steady_red_frames':len(states),'native_signal_actor_id':geometry['signal_actor_id'],
                     'stop_line_y_m':geometry['stop_line_y_m']},
            'method':'measure_signal','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_stop(attempt: Path,native: list[dict],geometry: dict):
    boundary=geometry['stop_line_y_m']
    crossing=None;halt=[];previous=None
    for index,sample in enumerate(native):
        front=max(v[1] for v in sample['native_body_xy_m'])
        speed=sample['speed_mps']
        if type(speed) not in (int,float) or not math.isfinite(speed) or speed<0:
            raise ValueError('Original speed absent')
        if crossing is None and previous is not None and previous<boundary<=front:
            crossing=index
        previous=front
        if speed<=.05 and front<boundary:halt.append(index)
    if crossing is None:raise ValueError('Original stop-line crossing absent')
    longest=0;span=0;prior=-2
    for index in (f for f in halt if f<crossing):
        span=span+1 if index==prior+1 else 1;longest=max(longest,span);prior=index
    if any(row.get('motorcycle_blueprint')!='vehicle.kawasaki.ninja' for row in native):
        raise ValueError('Qualified motorcycle source absent')
    return {'value':{'halt_before_right_turn_on_red':longest>=10,
                     'stationary_pre_crossing_frames':longest,
                     'first_front_crossing_frame':crossing},
            'method':'measure_stop','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_turn_yield(attempt: Path,native: list[dict],geometry: dict):
    if 'destination_crosswalk_x_m' not in geometry:
        raise ValueError('Original destination conflict readback absent')
    pedestrians=[i for i,row in enumerate(native) if row.get('walker_conflict_occupied') is True]
    traffic=[i for i,row in enumerate(native) if row.get('cross_traffic_conflict_occupied') is True]
    if not pedestrians or not traffic:
        raise ValueError('Original pedestrian or cross-traffic conflict source absent')
    occupied=sorted(set(pedestrians+traffic))
    entered=[i for i,row in enumerate(native) if row.get('ego_turn_entered') is True]
    if not occupied or not entered:raise ValueError('Original walker conflict or turn entry absent')
    first=entered[0];last=occupied[-1]
    end=native[-1]['native_center_xy_m']
    return {'value':{'turn_entry_frame':first,'last_walker_conflict_frame':pedestrians[-1],
                     'last_cross_traffic_conflict_frame':traffic[-1],
                     'sampled_clearance_s':round((first-last)/20,3),
                     'destination_exit_observed':end[0]>13 and abs(end[1]+1.75)<2},
            'method':'measure_turn_yield','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_right_turn_permission(attempt: Path,signal: dict,stop: dict,turn: dict,geometry: dict):
    lanes=geometry.get('lanes',{})
    approach=lanes.get('approach_right',{})
    destination=lanes.get('destination_right',{})
    if approach.get('lane_id')!=-1 or destination.get('lane_id')!=-1:
        raise ValueError('Extreme-right Native lane context absent')
    value={'steady_red_frames':signal['value']['steady_red_frames'],
           'pre_turn_full_halt':stop['value']['halt_before_right_turn_on_red'],
           'pre_crossing_stationary_frames':stop['value']['stationary_pre_crossing_frames'],
           'extreme_right_approach_lane':approach,
           'two_way_destination':lanes.get('destination_left',{}).get('lane_id')==1,
           'pedestrian_clearance_s':turn['value']['sampled_clearance_s'],
           'destination_exit_observed':turn['value']['destination_exit_observed']}
    return {'value':value,'method':'measure_right_turn_permission',
            'sources':{name:sha(source(attempt,name))
                       for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_two_cycles(attempt: Path,native: list[dict],geometry: dict):
    if not geometry.get('cross_signal_actor_id'):raise ValueError('Cross-signal actor survey absent')
    transitions=[];previous=None;cycles=0
    for index,row in enumerate(native):
        state=row.get('cross_signal_state_observed')
        if state not in ('Green','Yellow','Red','TrafficLightState.Green',
                         'TrafficLightState.Yellow','TrafficLightState.Red'):
            raise ValueError('Original cross-signal state absent')
        state=state.split('.')[-1]
        if previous and state!=previous:
            if (previous,state) not in (('Green','Yellow'),('Yellow','Red'),('Red','Green')):
                raise ValueError('Original cross-signal phase order differs')
            if previous=='Red' and state=='Green':cycles+=1
            transitions.append({'frame':index,'from':previous,'to':state})
        if row.get('complete_cross_signal_cycles')!=cycles:
            raise ValueError('Native cycle count differs from phase transitions')
        if row.get('fault_injection_command')!='withhold_motorcycle_detector_request':
            raise ValueError('Detector command source absent')
        previous=state
    entry=next((i for i,row in enumerate(native) if row.get('ego_turn_entered') is True),None)
    if entry is None:raise ValueError('Original turn entry absent')
    return {'value':{'complete_cycles_before_turn':native[entry]['complete_cross_signal_cycles'],
                     'two_complete_cycles_waited':native[entry]['complete_cross_signal_cycles']>=2,
                     'ego_steady_red_frames':len(native),'turn_entry_frame':entry,
                     'phase_transitions':transitions,
                     'fault_command_recorded':True,'physical_fault_causation_observed':False},
            'method':'measure_two_cycles','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_no_prohibition(attempt: Path,native: list[dict],geometry: dict):
    survey=geometry.get('turn_prohibition_survey')
    if not isinstance(survey,dict) or survey.get('authored_signs')!=[]:
        raise ValueError('Turn prohibition survey absent')
    if any(row.get('turn_prohibition_present') is not False for row in native):
        raise ValueError('Turn prohibition Native source absent')
    return {'value':{'authored_turn_prohibition_absent':True,
                     'native_sign_actors':survey.get('native_traffic_sign_actors',[]),
                     'physical_scene_independently_verified':False},
            'method':'measure_no_prohibition','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_witness_branch(attempt: Path,native: list[dict],geometry: dict):
    cycle=measure_two_cycles(attempt,native,geometry)
    return {'value':{'motorcycle_right_turn_failed_detection_witness':True,
                     'cycles_before_turn':cycle['value']['complete_cycles_before_turn'],
                     'fault_injection_recorded':True,'physical_failure_cause_verified':False},
            'method':'measure_witness_branch','sources':cycle['sources']}

def video_frames(path: Path):
    source(path.parent,path.name)
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
      '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
      text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(completed.stdout.strip())

def finalize(attempt: Path,output: Path):
    attempt=attempt.resolve();output=output.resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config=json.loads(source(attempt,'config.json').read_text())
    count=config['rate_hz']*config['duration_s']
    if count!=480:raise ValueError('Exact 480-frame contract differs')
    native,mapping,original=joins(attempt,count)
    geometry=json.loads(source(attempt,'road_geometry.json').read_text())
    signal=measure_signal(attempt,native,geometry)
    stop=measure_stop(attempt,native,geometry)
    turn=measure_turn_yield(attempt,native,geometry)
    cycle=measure_two_cycles(attempt,native,geometry)
    prohibition=measure_no_prohibition(attempt,native,geometry)
    witness=measure_witness_branch(attempt,native,geometry)
    permission=measure_right_turn_permission(attempt,signal,stop,turn,geometry)
    videos=[f'{name}.mkv' for name in ('overview','approach','signal','destination')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(value!=count for value in counts.values()):
        raise ValueError('Original source video frame count differs')
    expected=config['case_suffix']=='condition_a'
    observed=cycle['value']['two_complete_cycles_waited']
    recording=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];relative='channels/'+name+'.jsonl'
        source(attempt,relative)
        recording.append({'name':name,'unit':channel['unit'],'reference':relative})
    result={'case_id':config['case_id'],
        'measured_values':{'signal':signal['value'],'stop':stop['value'],
                           'turn_yield':turn['value'],'right_turn_permission':permission['value'],
                           'two_cycles':cycle['value'],'no_prohibition':prohibition['value']},
        'target_checks':[{'target':'two complete signal cycles before motorcycle right turn',
            'requested':expected,'measured':observed,'method':'saved original cross-signal phase transitions before turn entry',
            'tolerance':0,'matched':observed==expected,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','road_geometry.json']}],
        'setup_confirmed':True,'behavior_attempted':True,
        'maneuver_completed':turn['value']['destination_exit_observed'],
        'termination_reason':'full original duration retained',
        'physical_failure_flags':['original_signal_direction_pixels_and_detector_cause_require_independent_review']+
            ([] if observed==expected and turn['value']['destination_exit_observed']
             else ['controlled_behavior_or_turn_unconfirmed']),
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':recording,
        'realized_observables':{'first_front_stop_line_crossing_frame':{
            'value':stop['value']['first_front_crossing_frame'],'unit':'frame',
            'method':'source-hashed sampled full-body stop-line crossing',
            'time_window':'entire original 24 s attempt','statistic':'first',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110919-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'steady_red_activation':signal,
                            'motorcycle_stop':stop,'two_cycle_fault_condition':cycle,
                            'no_turn_prohibition':prohibition,'pedestrian_and_traffic_yield':turn,
                            'failed_detection_witness':witness},
            'original_joins':original,'video_frames':counts,
            'scope':'saved original Native sources and decoded original video; not independent acceptance or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))

if __name__=='__main__':main()

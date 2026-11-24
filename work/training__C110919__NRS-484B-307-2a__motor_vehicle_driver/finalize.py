"""Saved-only circular-green right-turn and lawful-user yield analysis."""
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
    if not states or any(state not in ('Green','TrafficLightState.Green','circular_green') for state in states):
        raise ValueError('Original governing circular-green state absent')
    if not geometry.get('signal_actor_id') or geometry.get('stop_line_y_m')!=-14.0:
        raise ValueError('Original signal and lane readback absent')
    return {'value':{'circular_green_frames':len(states),'native_signal_actor_id':geometry['signal_actor_id'],
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
    return {'value':{'full_halt_before_line_incidental':longest>=10,
                     'stationary_pre_crossing_frames':longest,
                     'first_front_crossing_frame':crossing},
            'method':'measure_stop','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_turn_yield(attempt: Path,native: list[dict],geometry: dict):
    if 'destination_crosswalk_x_m' not in geometry:
        raise ValueError('Original destination conflict readback absent')
    pedestrians=[i for i,row in enumerate(native) if row.get('walker_conflict_occupied') is True]
    traffic=[i for i,row in enumerate(native) if row.get('cross_traffic_conflict_occupied') is True]
    entered=[i for i,row in enumerate(native) if row.get('ego_turn_entered') is True]
    if not pedestrians or not traffic or not entered:
        raise ValueError('Original lawful-user conflict or turn entry absent')
    first=entered[0];last=max(pedestrians[-1],traffic[-1])
    end=native[-1]['native_center_xy_m']
    return {'value':{'turn_entry_frame':first,'last_walker_conflict_frame':pedestrians[-1],
                     'last_cross_traffic_conflict_frame':traffic[-1],
                     'yielded_to_lawful_users':first>last,
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
    prohibition=measure_no_turn_prohibition(attempt,rows(source(attempt,'native_samples.jsonl')),geometry)
    value={'circular_green_frames':signal['value']['circular_green_frames'],
           'extreme_right_approach_lane':approach,
           'two_way_destination':lanes.get('destination_left',{}).get('lane_id')==1,
           'lawful_user_clearance_s':turn['value']['sampled_clearance_s'],
           'yielded_to_lawful_users':turn['value']['yielded_to_lawful_users'],
           'no_turn_prohibition':prohibition['value']['authored_turn_prohibition_absent'],
           'destination_exit_observed':turn['value']['destination_exit_observed']}
    return {'value':value,'method':'measure_right_turn_permission',
            'sources':{name:sha(source(attempt,name))
                       for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_no_turn_prohibition(attempt: Path,native: list[dict],geometry: dict):
    survey=geometry.get('turn_prohibition_survey')
    if not isinstance(survey,dict) or survey.get('authored_signs')!=[]:
        raise ValueError('Turn prohibition survey absent')
    if any(row.get('turn_prohibition_present') is not False for row in native):
        raise ValueError('Turn prohibition source absent')
    return {'value':{'authored_turn_prohibition_absent':True,
                     'native_sign_actors':survey.get('native_traffic_sign_actors',[]),
                     'original_pixels_independently_reviewed':False},
            'method':'measure_no_turn_prohibition','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_witness_branch(attempt: Path,native: list[dict],geometry: dict):
    signal=measure_signal(attempt,native,geometry)
    turn=measure_turn_yield(attempt,native,geometry)
    return {'value':{'right_turn_under_circular_green_alone':True,
                     'yielded_to_lawful_users':turn['value']['yielded_to_lawful_users'],
                     'no_turn_prohibition':measure_no_turn_prohibition(attempt,native,geometry)['value']['authored_turn_prohibition_absent']},
            'method':'measure_witness_branch','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def video_frames(path: Path):
    source(path.parent,path.name)
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
      '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
      text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(completed.stdout.strip())

def rebuild_channels(attempt: Path, native: list[dict], mapping: list[dict],
                     geometry: dict, config: dict):
    """Create derived observations from retained source rows, never fixture channels."""
    destination=attempt/'channels'
    if destination.exists():raise ValueError('Retain prior derived channels; use a fresh attempt')
    destination.mkdir()
    names={item['name'] for item in config['recording_description']['channels']}
    expected={'dev.traffic_signal','dev.governs','dev.regulatory_sign','drv.turning',
              'drv.entering_intersection','ru.pedestrian','drv.in_intersection',
              'drv.arrival_order','st.stop_line','st.crosswalk','drv.stopped',
              'kin.velocity','drv.extreme_lane','st.one_way_roadway',
              'drv.yields_to','native_body_pose_control','camera_frame_join'}
    if names!=expected:raise ValueError('Declared saved observation channels differ')
    for name in sorted(names):
        lines=[]
        for sample, frame in zip(native,mapping):
            if sample['native_frame']!=frame['native_frame'] or \
                    abs(sample['time_s']-frame['time_s'])>1e-4:
                raise ValueError('Derived channel source frame join differs')
            if name=='dev.traffic_signal':
                value={'observed_state':sample['signal_state_observed'],
                       'native_actor_id':geometry['signal_actor_id']}
            elif name=='dev.governs':value={
                'native_actor_id':geometry['signal_actor_id'],
                'approach_lane':geometry['lanes']['approach_right'],
                'physical_direction_reviewed':False}
            elif name=='dev.regulatory_sign':value={
                'turn_prohibition_present':sample['turn_prohibition_present'],
                'survey':geometry['turn_prohibition_survey'],
                'original_pixels_reviewed':False}
            elif name=='drv.turning':value={
                'turn_entry_observed':sample['ego_turn_entered'],
                'yaw_deg':sample['native_yaw_deg']}
            elif name=='drv.entering_intersection':value={
                'body_front_y_m':max(v[1] for v in sample['native_body_xy_m']),
                'near_boundary_y_m':-7.0}
            elif name=='ru.pedestrian':value={
                'center_xy_m':sample['walker_center_xy_m'],
                'conflict_occupied':sample['walker_conflict_occupied'],
                'lawful_presence_verified':False}
            elif name=='drv.in_intersection':value={
                'cross_traffic_actor_id':sample['cross_traffic_actor_id'],
                'center_xy_m':sample['cross_traffic_center_xy_m'],
                'conflict_occupied':sample['cross_traffic_conflict_occupied'],
                'lawful_presence_verified':False}
            elif name=='drv.arrival_order':value={
                'native_frame':sample['native_frame'],
                'signal_state':sample['signal_state_observed'],
                'walker_conflict_occupied':sample['walker_conflict_occupied'],
                'cross_traffic_conflict_occupied':sample['cross_traffic_conflict_occupied'],
                'ego_turn_entered':sample['ego_turn_entered']}
            elif name=='st.stop_line':value=geometry['stop_line_y_m']
            elif name=='st.crosswalk':value=geometry['nearest_crosswalk_y_m']
            elif name=='drv.stopped':value=sample['speed_mps']<.05
            elif name=='kin.velocity':value=sample['speed_mps']
            elif name=='drv.extreme_lane':value=geometry['lanes']['approach_right']
            elif name=='st.one_way_roadway':value=geometry['lanes']
            elif name=='drv.yields_to':value={
                'walker_conflict_occupied':sample['walker_conflict_occupied'],
                'cross_traffic_conflict_occupied':sample['cross_traffic_conflict_occupied']}
            elif name=='native_body_pose_control':value=sample
            else:value=frame
            lines.append(json.dumps({'time_s':sample['time_s'],'value':value},
                                    allow_nan=False)+'\n')
        (destination/(name+'.jsonl')).write_text(''.join(lines))

def finalize(attempt: Path,output: Path):
    attempt=attempt.resolve();output=output.resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config=json.loads(source(attempt,'config.json').read_text())
    count=config['rate_hz']*config['duration_s']
    if count!=600:raise ValueError('Exact 600-frame contract differs')
    native,mapping,original=joins(attempt,count)
    geometry=json.loads(source(attempt,'road_geometry.json').read_text())
    signal=measure_signal(attempt,native,geometry)
    stop=measure_stop(attempt,native,geometry)
    turn=measure_turn_yield(attempt,native,geometry)
    prohibition=measure_no_turn_prohibition(attempt,native,geometry)
    witness=measure_witness_branch(attempt,native,geometry)
    permission=measure_right_turn_permission(attempt,signal,stop,turn,geometry)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(value!=count for value in counts.values()):
        raise ValueError('Original source video frame count differs')
    rebuild_channels(attempt,native,mapping,geometry,config)
    expected=config['case_suffix']=='controlled_1'
    observed=turn['value']['yielded_to_lawful_users']
    recording=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];relative='channels/'+name+'.jsonl'
        source(attempt,relative)
        recording.append({'name':name,'unit':channel['unit'],'reference':relative})
    result={'case_id':config['case_id'],
        'measured_values':{'signal':signal['value'],'stop':stop['value'],
                           'turn_yield':turn['value'],'right_turn_permission':permission['value'],
                           'no_turn_prohibition':prohibition['value']},
        'target_checks':[{'target':'yielded to lawful pedestrian and cross traffic before right turn',
            'requested':expected,'measured':observed,'method':'saved original actor conflict occupancy and ego turn entry',
            'tolerance':0,'matched':observed==expected,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','road_geometry.json']}],
        'setup_confirmed':True,'behavior_attempted':True,
        'maneuver_completed':turn['value']['destination_exit_observed'],
        'termination_reason':'full original duration retained',
        'physical_failure_flags':['original_signal_direction_and_pixels_require_independent_review']+
            ([] if observed==expected and turn['value']['destination_exit_observed']
             else ['controlled_behavior_or_turn_unconfirmed']),
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':recording,
        'realized_observables':{'first_front_stop_line_crossing_frame':{
            'value':stop['value']['first_front_crossing_frame'],'unit':'frame',
            'method':'source-hashed sampled full-body stop-line crossing',
            'time_window':'entire original 30 s attempt','statistic':'first',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':('synthetic_local_diagnostic' if json.loads(
            source(attempt,'capture/manifest.json').read_text()).get('synthetic_diagnostic')
            else 'native'),'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110919-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'circular_green_activation':signal,
                            'right_turn_no_prohibition':permission,
                            'lawful_user_yield':turn,
                            'right_turn_green_witness':witness},
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

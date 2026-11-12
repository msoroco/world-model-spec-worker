"""Saved-only C110919 pedestrian-conflict pair analysis; no legal verdict."""
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

def measure_signal(attempt: Path,native: list[dict],geometry: dict,case_suffix: str|None=None):
    states=[sample.get('signal_state_observed') for sample in native]
    red=('Red','TrafficLightState.Red','steady_red')
    green=('Green','TrafficLightState.Green')
    green_release=case_suffix in ('green_release_wait','green_release_red_turn')
    if green_release:
        if len(states)!=480 or any(state not in red for state in states[:160]) or \
           any(state not in green for state in states[160:]):
            raise ValueError('Original governing red-to-green transition differs')
    elif not states or any(state not in red for state in states):
        raise ValueError('Original governing steady red state absent')
    absent=geometry.get('stopping_reference_kind')=='intersection_boundary'
    reference=geometry.get('stopping_reference_y_m',geometry.get('stop_line_y_m'))
    if not geometry.get('signal_actor_id') or reference!=(-7.0 if absent else -14.0):
        raise ValueError('Original signal/stop reference readback absent')
    if absent and (geometry.get('stop_line_y_m') is not None or
                   geometry.get('nearest_crosswalk_y_m') is not None or
                   geometry.get('intersection_near_y_m')!=-7.0):
        raise ValueError('Absent-reference branch still has a marked stop reference')
    return {'value':{'steady_red_frames':160 if green_release else len(states),
                     'green_frames':len(states)-160 if green_release else 0,
                     'first_green_frame':160 if green_release else None,
                     'native_signal_actor_id':geometry['signal_actor_id'],
                     'stopping_reference_kind':'intersection_boundary' if absent else 'marked_stop_line',
                     'stopping_reference_y_m':reference},
            'method':'measure_signal','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_stop(attempt: Path,native: list[dict],geometry: dict):
    boundary=geometry.get('stopping_reference_y_m',geometry.get('stop_line_y_m'))
    if type(boundary) not in (int,float):raise ValueError('Original stopping boundary absent')
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
    if crossing is None:raise ValueError('Original stopping-reference crossing absent')
    longest=0;span=0;prior=-2
    for index in (f for f in halt if f<crossing):
        span=span+1 if index==prior+1 else 1;longest=max(longest,span);prior=index
    return {'value':{'halt_before_nearest_boundary':longest>=10,
                     'stationary_pre_crossing_frames':longest,
                     'first_front_crossing_frame':crossing,
                     'stopping_reference_y_m':boundary},
            'method':'measure_stop','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_green_release(attempt: Path,native: list[dict],signal: dict,stop: dict):
    first_green=signal['value']['first_green_frame']
    crossing=stop['value']['first_front_crossing_frame']
    if first_green is None or not stop['value']['halt_before_nearest_boundary']:
        raise ValueError('Green-release comparison requires red stop and green transition')
    held=stop['value']['stationary_pre_crossing_frames']
    if held<10 or crossing<10:
        raise ValueError('Green-release full-body stop interval absent')
    boundary=stop['value']['stopping_reference_y_m']
    stop_start=next((i for i,row in enumerate(native[:crossing])
                     if row['speed_mps']<=.05 and
                     max(v[1] for v in row['native_body_xy_m'])<boundary),None)
    if stop_start is None:
        raise ValueError('Green-release first stationary full-body sample absent')
    stationary_until_green=(crossing>=first_green and
        all(row['speed_mps']<=.05 and
            max(v[1] for v in row['native_body_xy_m'])<boundary
            for row in native[stop_start:first_green]))
    return {'value':{'first_green_frame':first_green,
                     'first_front_crossing_frame':crossing,
                     'first_stationary_frame':stop_start,
                     'remain_stopped_until_green':stationary_until_green,
                     'stationary_pre_crossing_frames':held},
            'method':'measure_green_release',
            'sources':{name:sha(source(attempt,name)) for name in
                       ('native_samples.jsonl','road_geometry.json')}}

def measure_turn_yield(attempt: Path,native: list[dict],geometry: dict):
    if 'destination_crosswalk_x_m' not in geometry:
        raise ValueError('Original destination conflict readback absent')
    occupied=[i for i,row in enumerate(native) if row.get('walker_conflict_occupied') is True]
    entered=[i for i,row in enumerate(native) if row['native_center_xy_m'][0]>=8 and
             row['native_center_xy_m'][1]>-7]
    if not occupied or not entered:raise ValueError('Original walker conflict or turn entry absent')
    first=entered[0];last=occupied[-1]
    end=native[-1]['native_center_xy_m']
    return {'value':{'turn_entry_frame':first,'last_walker_conflict_frame':last,
                     'sampled_clearance_s':round((first-last)/20,3),
                     'destination_exit_observed':end[0]>13 and abs(end[1]+1.75)<2},
            'method':'measure_turn_yield','sources':{name:sha(source(attempt,name))
                for name in ('native_samples.jsonl','road_geometry.json')}}

def measure_yield_branch(attempt: Path,native: list[dict],suffix: str):
    if suffix not in ('yield_wait','yield_conflict_entry'):
        raise ValueError('Unknown exact pedestrian-conflict branch')
    occupied=[];overlap=[];body_entry=[]
    for index,row in enumerate(native):
        if row.get('yield_policy')!=suffix:
            raise ValueError('Saved yield policy differs from exact case')
        walker=row.get('walker_center_xy_m')
        if not isinstance(walker,list) or len(walker)!=2:
            raise ValueError('Saved walker center absent')
        observed=8<=walker[0]<=12 and -4<=walker[1]<=4
        if row.get('walker_conflict_occupied') is not observed:
            raise ValueError('Saved walker occupancy differs from center')
        body=row['native_body_xy_m']
        in_zone=max(v[0] for v in body)>=8 and min(v[0] for v in body)<=12 and \
                max(v[1] for v in body)>=-4 and min(v[1] for v in body)<=4
        if observed:occupied.append(index)
        if in_zone:
            body_entry.append(index)
            if observed:overlap.append(index)
    if not occupied or not body_entry:
        raise ValueError('Saved pedestrian conflict or ego body entry absent')
    return {'value':{'first_body_conflict_frame':body_entry[0],
                     'first_pedestrian_conflict_frame':occupied[0],
                     'last_pedestrian_conflict_frame':occupied[-1],
                     'body_pedestrian_overlap_frames':overlap},
            'method':'measure_yield_branch','sources':{'native_samples.jsonl':
                sha(source(attempt,'native_samples.jsonl'))}}

def video_frames(path: Path):
    source(path.parent,path.name)
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
      '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
      text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(completed.stdout.strip())


def derive_channels(attempt: Path,config: dict,native: list[dict],mapping: list[dict],geometry: dict):
    """Rebuild observations from retained raw rows rather than incoming channels."""
    names={item['name'] for item in config['recording_description']['channels']}
    output={name:[] for name in names}
    if len(native)!=len(mapping)!=480:raise ValueError('Original channel source counts differ')
    for sample,frame in zip(native,mapping):
        if sample['native_frame']!=frame['native_frame'] or abs(sample['time_s']-frame['time_s'])>1e-4:
            raise ValueError('Original channel frame/time join differs')
        speed=sample['speed_mps']
        values={
            'dev.traffic_signal':{'observed_state':sample['signal_state_observed'],
                                  'native_actor_id':geometry['signal_actor_id']},
            'st.stop_line':(geometry['stop_line_y_m'] if geometry['stop_line_y_m'] is not None
                            else {'present':False,'source':'road_geometry.json',
                                  'native_map_sha256':geometry['native_map_sha256']}),
            'st.crosswalk':(geometry['nearest_crosswalk_y_m'] if geometry['nearest_crosswalk_y_m'] is not None
                            else {'present':False,'source':'road_geometry.json',
                                  'native_map_sha256':geometry['native_map_sha256']}),
            'drv.stopped':speed<.05,
            'kin.velocity':speed,
            'drv.extreme_lane':geometry['lanes']['approach_right'],
            'st.one_way_roadway':geometry['lanes'],
            'drv.yields_to':{'walker_xy_m':sample['walker_center_xy_m'],
                             'conflict_occupied':sample['walker_conflict_occupied'],
                             'legal_yield_verdict':None},
            'native_body_pose_control':sample,
            'camera_frame_join':frame}
        if set(values)!=names:raise ValueError('Declared channels differ from raw derivation')
        for name,value in values.items():
            output[name].append(json.dumps({'time_s':frame['time_s'],'value':value},
                                          allow_nan=False)+'\n')
    folder=attempt/'channels';folder.mkdir(exist_ok=True)
    for name,values in output.items():
        (folder/(name+'.jsonl')).write_text(''.join(values))

def finalize(attempt: Path,output: Path):
    attempt=attempt.resolve();output=output.resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config=json.loads(source(attempt,'config.json').read_text())
    count=config['rate_hz']*config['duration_s']
    if count!=480:raise ValueError('Exact 480-frame contract differs')
    native,mapping,original=joins(attempt,count)
    geometry=json.loads(source(attempt,'road_geometry.json').read_text())
    capture_manifest=json.loads(source(attempt,'capture/manifest.json').read_text())
    geometry_synthetic=geometry.get('synthetic_diagnostic') is True
    capture_synthetic=capture_manifest.get('synthetic_diagnostic') is True
    if geometry_synthetic!=capture_synthetic:
        raise ValueError('Saved source provenance markers disagree')
    diagnostic_fixture=geometry_synthetic
    if diagnostic_fixture:
        trace=rows(source(attempt,'trace.jsonl'))
        evidence=rows(source(attempt,'capture/evidence.jsonl'))
        if not all(row.get('synthetic_diagnostic') is True and
                   row.get('speed_provenance')=='synthetic_native_sample'
                   for group in (trace,native) for row in group) or not all(
                       row.get('synthetic_diagnostic') is True and
                       row.get('ego',{}).get('speed_provenance')=='synthetic_native_sample'
                       for row in evidence):
            raise ValueError('Synthetic speed must retain diagnostic provenance')
    suffix=config['case_suffix']
    if suffix not in ('yield_wait','yield_conflict_entry'):
        raise ValueError('Use exact pedestrian-conflict case')
    signal=measure_signal(attempt,native,geometry,suffix)
    stop=measure_stop(attempt,native,geometry)
    green_release=(measure_green_release(attempt,native,signal,stop)
                   if suffix in ('green_release_wait','green_release_red_turn') else None)
    turn=measure_turn_yield(attempt,native,geometry)
    yield_branch=measure_yield_branch(attempt,native,suffix)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(value!=count for value in counts.values()):
        raise ValueError('Original source video frame count differs')
    expected=True
    observed=stop['value']['halt_before_nearest_boundary']
    expected_overlap=suffix=='yield_conflict_entry'
    observed_overlap=bool(yield_branch['value']['body_pedestrian_overlap_frames'])
    derive_channels(attempt,config,native,mapping,geometry)
    recording=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];relative='channels/'+name+'.jsonl'
        source(attempt,relative)
        recording.append({'name':name,'unit':channel['unit'],'reference':relative})
    context_values={
        'four_source_cameras':counts,
        'surveyed_C110919_intersection':{
            'native_map_sha256':geometry['native_map_sha256'],
            'signal_actor_id':geometry['signal_actor_id'],
            'lanes':geometry['lanes']}}
    context_folder=attempt/'context';context_folder.mkdir(exist_ok=True)
    for context in config['recording_description']['context_inputs']:
        name=context['name']
        if name not in context_values:raise ValueError('Undeclared yield-branch context input')
        relative='context/'+name+'.json'
        (attempt/relative).write_text(json.dumps({name:context_values[name]},allow_nan=False)+'\n')
        recording.append({'name':name,'unit':context['unit'],'reference':relative})
    result={'case_id':config['case_id'],
        'measured_values':{'signal':signal['value'],'stop':stop['value'],'turn_yield':turn['value'],
                           'yield_branch':yield_branch['value'],
                           **({'green_release':green_release['value']} if green_release else {})},
        'target_checks':[{'target':'authored controlled halt before marked stopping reference',
            'requested':expected,'measured':observed,'method':'saved original full body, speed and signal before stopping-reference crossing',
            'tolerance':0,'matched':observed==expected,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','road_geometry.json']},
            {'target':'ego body and pedestrian conflict-zone sample overlap',
             'requested':expected_overlap,'measured':observed_overlap,
             'method':'saved Native full-body and pedestrian-center overlap',
             'tolerance':0,'matched':observed_overlap==expected_overlap,
             'physical_cause_confirmed':False,
             'cause_evidence':['native_samples.jsonl']}],
        'setup_confirmed':not diagnostic_fixture,'behavior_attempted':not diagnostic_fixture,
        'maneuver_completed':not diagnostic_fixture and turn['value']['destination_exit_observed'],
        'termination_reason':'full original duration retained',
        'physical_failure_flags':['original_signal_direction_and_pixels_require_independent_review']+
            ([] if observed==expected and observed_overlap==expected_overlap and turn['value']['destination_exit_observed']
             else ['controlled_behavior_or_turn_unconfirmed']),
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],
        'recording_evidence':recording,
        'realized_observables':{'first_front_stop_line_crossing_frame':{
            'value':stop['value']['first_front_crossing_frame'],'unit':'frame',
            'method':'source-hashed sampled full-body stopping-reference crossing',
            'time_window':'entire original 24 s attempt','statistic':'first',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':'synthetic_local_diagnostic' if diagnostic_fixture else 'native',
        'diagnostic_fixture':diagnostic_fixture,
        'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110919-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'steady_red_activation':signal,
                            'right_turn_stop':stop,'right_turn_yield':turn,
                            'pedestrian_conflict_branch':yield_branch,
                            **({'green_release':green_release} if green_release else {})},
            'original_joins':original,'video_frames':counts,
            'provenance_kind':result['provenance_kind'],
            'scope':('synthetic CPU saved sources and decoded synthetic video' if diagnostic_fixture
                     else 'saved original Native sources and decoded original video')+
                    '; not independent acceptance or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))

if __name__=='__main__':main()

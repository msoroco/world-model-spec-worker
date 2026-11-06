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

def measure_cited_exception(attempt: Path,native: list[dict],geometry: dict):
    flags={(r.get('pedestrian_blind_declared'),r.get('white_cane_declared')) for r in native}
    if len(flags)!=1 or next(iter(flags)) not in ((False,False),(True,True)):
        raise ValueError('Cited blind-white-cane exception source differs')
    present=next(iter(flags))[0]
    if any(r.get('white_cane_visual_prop_physically_verified') is not False for r in native):
        raise ValueError('Unreviewed cane physical claim')
    return {'value':{'blind_white_cane_exception_declared':present,
                     'physical_cane_and_eligibility_verified':False,
                     'cited_source':'NRS 484B.290 [LVMC-11-30-140-B]'},
            'method':'measure_cited_exception','sources':{n:sha(source(attempt,n))
                for n in ('native_samples.jsonl','road_geometry.json')}}

def measure_crosswalk_yield(attempt: Path,native: list[dict],geometry: dict):
    if geometry.get('official_signal_actors_present') is not False or geometry.get('nearest_crosswalk_y_m')!=-11.0:
        raise ValueError('Uncontrolled marked-crosswalk survey absent')
    if any(r.get('official_device_actors_present') is not False or r.get('crosswalk_marked') is not True or
           r.get('pedestrian_on_ego_highway_half') is not True for r in native):
        raise ValueError('Uncontrolled ego-half crosswalk source differs')
    occupied=[i for i,r in enumerate(native) if r.get('walker_conflict_occupied') is True]
    overlap=[i for i,r in enumerate(native) if max(v[1] for v in r['native_body_xy_m'])>=-12 and
             min(v[1] for v in r['native_body_xy_m'])<=-10]
    if not occupied or not overlap:raise ValueError('Pedestrian or full-body crosswalk source absent')
    conflict=sorted(set(occupied)&set(overlap))
    first=overlap[0]
    stationary=[]
    for i,r in enumerate(native[:first]):
        if r['speed_mps']<=.05 and max(v[1] for v in r['native_body_xy_m'])<-12:stationary.append(i)
    longest=0;run=0;prior=-2
    for i in stationary:
        run=run+1 if i==prior+1 else 1;longest=max(longest,run);prior=i
    return {'value':{'first_ego_crosswalk_overlap_frame':first,
                     'last_pedestrian_ego_half_frame':occupied[-1],
                     'ego_pedestrian_overlap_frames':conflict,
                     'yielded_to_crosswalk_pedestrian':not conflict,
                     'full_halt_before_crosswalk':longest>=10,
                     'pre_crosswalk_stationary_frames_contiguous':longest,
                     'departure_observed':native[-1]['native_center_xy_m'][1]>13},
            'method':'measure_crosswalk_yield','sources':{n:sha(source(attempt,n))
                for n in ('native_samples.jsonl','road_geometry.json')}}

def measure_directional_half(attempt: Path,native: list[dict],geometry: dict):
    lanes=geometry.get('lanes',{})
    if lanes.get('approach_ego_half',{}).get('lane_id')!=-1 or lanes.get('departure_ego_half',{}).get('lane_id')!=-1:
        raise ValueError('Native directional highway-half lane survey absent')
    if any(r.get('road_one_way') is not False or r.get('ego_directional_lanes')!=[-1] for r in native):
        raise ValueError('Directional highway-half source differs')
    return {'value':{'road_one_way':False,'ego_directional_lane_ids':[-1],
                     'pedestrian_on_ego_half_frames':sum(r['pedestrian_on_ego_highway_half'] is True for r in native),
                     'half_definition':'all lanes designated for ego travel direction'},
            'method':'measure_directional_half','sources':{n:sha(source(attempt,n))
                for n in ('native_samples.jsonl','road_geometry.json')}}

def measure_witness_branch(attempt: Path,native: list[dict],geometry: dict):
    crossing=measure_crosswalk_yield(attempt,native,geometry)
    exception=measure_cited_exception(attempt,native,geometry)
    return {'value':{'crosswalk_on_ego_highway_half':True,
                     'yielded_to_crosswalk_pedestrian':crossing['value']['yielded_to_crosswalk_pedestrian'],
                     'blind_white_cane_exception_declared':exception['value']['blind_white_cane_exception_declared'],
                     'physical_exception_verified':False},
            'method':'measure_witness_branch','sources':crossing['sources']}

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
    exception=measure_cited_exception(attempt,native,geometry)
    crossing=measure_crosswalk_yield(attempt,native,geometry)
    half=measure_directional_half(attempt,native,geometry)
    witness=measure_witness_branch(attempt,native,geometry)
    videos=[f'{name}.mkv' for name in ('overview','approach','signal','destination')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(v!=count for v in counts.values()):raise ValueError('Original video frame count differs')
    suffix=config['case_suffix']
    if suffix in ('witness_1','witness_2'):
        target='crosswalk_pedestrian_yield';expected=suffix=='witness_1'
        observed=crossing['value']['yielded_to_crosswalk_pedestrian']
    else:
        target='blind_white_cane_exception_applicability';expected=suffix=='exception_1_2'
        observed=exception['value']['blind_white_cane_exception_declared']
    recording=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];relative='channels/'+name+'.jsonl';source(attempt,relative)
        recording.append({'name':name,'unit':channel['unit'],'reference':relative})
    result={'case_id':config['case_id'],
        'measured_values':{'exception':exception['value'],'crosswalk_yield':crossing['value'],
                           'directional_half':half['value'],'witness':witness['value']},
        'target_checks':[{'target':target,'requested':expected,'measured':observed,
            'method':'saved source-hashed original full body, pedestrian occupancy and exception declaration',
            'tolerance':0,'matched':observed==expected,'physical_cause_confirmed':False,
            'cause_evidence':['native_samples.jsonl','road_geometry.json']}],
        'setup_confirmed':True,'behavior_attempted':True,
        'maneuver_completed':crossing['value']['departure_observed'],
        'termination_reason':'full original duration retained',
        'physical_failure_flags':['pedestrian_eligibility_cane_pixels_and_device_absence_require_independent_review']+
            ([] if observed==expected and crossing['value']['departure_observed'] else ['controlled_behavior_unconfirmed']),
        'trace_reference':'trace.jsonl','video_references':videos,
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':config['recording_description'],'recording_evidence':recording,
        'realized_observables':{'first_ego_crosswalk_overlap_frame':{
            'value':crossing['value']['first_ego_crosswalk_overlap_frame'],'unit':'frame',
            'method':'source-hashed original full-body crosswalk overlap',
            'time_window':'entire original 24 s attempt','statistic':'first',
            'reference':'native_samples.jsonl'}},
        'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c111256-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'cited_exception_condition':exception,
                            'uncontrolled_crosswalk_yield':crossing,
                            'directional_highway_half':half,
                            'ego_half_crosswalk_witness':witness},
            'original_joins':original,'video_frames':counts,
            'scope':'saved Native sources and decoded video; no independent acceptance or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))

if __name__=='__main__':main()

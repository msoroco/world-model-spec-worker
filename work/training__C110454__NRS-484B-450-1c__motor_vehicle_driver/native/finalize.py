"""Saved-only C110454 finalization proposal; no legal or acceptance verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure import measure


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError("Missing required source: "+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_original_joins(attempt,expected_frames):
    attempt=Path(attempt)
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    body=rows(attempt/'body_history.jsonl')
    if not all(len(source)==expected_frames for source in (trace,evidence,mapping,motion,body)):
        raise ValueError("Original trace/evidence/body/frame counts differ")
    previous_frame=-1;previous_time=-math.inf
    for index,(t,e,m,n,b) in enumerate(zip(trace,evidence,mapping,motion,body)):
        frame=m.get('native_frame');time=float(m['time_s'])
        if frame<=previous_frame or time<=previous_time or m['video_frame']!=index:
            raise ValueError("Original frame/time mapping is not monotonic")
        previous_frame=frame;previous_time=time
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),n.get('native_frame'),b.get('frame'))):
            raise ValueError("Original Native frame join differs")
        if any(abs(float(item)-time)>1e-4 for item in
               (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'])):
            raise ValueError("Original Native timestamp join differs")
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in n['native_body_xy_m']}
        body_history={(round(v[0],5),round(v[1],5)) for v in b['body_vertices_m']}
        if captured!=measured or measured!=body_history or len(measured)!=4:
            raise ValueError("Original full body differs from saved measurement")
    meta=json.loads((attempt/'capture/manifest.json').read_text())
    if not meta.get('extraction_confirmed') or meta.get('frames')!=expected_frames:
        raise ValueError("Original capture extraction incomplete")
    return {'frames':expected_frames,'first_frame':mapping[0]['native_frame'],
            'last_frame':mapping[-1]['native_frame'],
            'first_time_s':mapping[0]['time_s'],'last_time_s':mapping[-1]['time_s'],
            'source_hashes':{name:sha(attempt/name) for name in
              ('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
               'native_samples.jsonl','body_history.jsonl','capture/manifest.json')}}


def video_frames(path):
    if not path.is_file():raise ValueError("Missing required source: "+path.name)
    completed=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError("Source video decode failed: "+path.name+" "+completed.stderr[-300:])
    return int(completed.stdout.strip())


def measure_park(attempt):
    attempt=Path(attempt)
    source=attempt/'native_samples.jsonl'
    samples=rows(source)
    survey_path=attempt/'road_geometry.json'
    if not survey_path.is_file():raise ValueError('Missing required source: road_geometry.json')
    survey=json.loads(survey_path.read_text())
    if survey.get('intersection_polygon_xy_m')!=[[-7,-7],[7,-7],[7,7],[-7,7]]:
        raise ValueError('Original Native intersection polygon differs')
    if survey.get('native_signal_count')!=0:
        raise ValueError('Unexpected original Native signal in no-device probe')
    result=measure(source,sha(source))
    return {'value':result,
            'method':'measure_park',
            'sources':{name:sha(attempt/name) for name in ('native_samples.jsonl','road_geometry.json')}}


def measure_unexcepted_stop(attempt):
    parked=measure_park(attempt)
    return {'value':parked['value']['parked_frames']>=40 and
            parked['value']['exception_flags_all_false'] is True,
            'method':'measure_unexcepted_stop','sources':parked['sources']}


def measure_witness(attempt):
    parked=measure_park(attempt)
    return {'value':parked['value']['parking_relation']=='within_intersection',
            'method':'measure_witness','sources':parked['sources']}


def derive_channels(attempt,description):
    """Reconstruct recording channels from retained original source rows only."""
    attempt=Path(attempt)
    destination=attempt/'channels'
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Preexisting derived channels cannot replace original sources')
    destination.mkdir(exist_ok=True)
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    survey=json.loads((attempt/'road_geometry.json').read_text())
    if len(motion)!=len(mapping):
        raise ValueError('Native motion/frame mapping length differs')
    by_name={name:[] for name in (item['name'] for item in description['channels'])}
    for sample,frame in zip(motion,mapping):
        if sample['native_frame']!=frame['native_frame'] or sample['time_s']!=frame['time_s']:
            raise ValueError('Derived channel Native frame/time join differs')
        speed=sample['speed_m_s']
        values={
            'drv.standing_or_parked':{'speed_m_s':speed},
            'st.intersection':survey,
            'rel.occupies':{'body_xy_m':sample['body_xy_m'],
                            'intersection_polygon_xy_m':survey['intersection_polygon_xy_m']},
            'drv.forced_halt':{'traffic_conflict':sample['exceptions']['traffic_conflict'],
                               'other_traffic_actor_count':sample['exception_source']['other_traffic_actor_count']},
            'dev.human_direction':{'police_direction':sample['exceptions']['police_direction'],
                                   'authored_law_direction_count':sample['exception_source']['authored_law_direction_count']},
            'dev.traffic_signal':{'traffic_device':sample['exceptions']['traffic_device'],
                                  'native_signal_count':sample['exception_source']['native_signal_count']},
            'kin.velocity':{'speed_m_s':speed},
            'native_body_pose_control':sample,
            'camera_frame_join':frame}
        for name in by_name:
            if name not in values:
                raise ValueError('No source-derived channel mapping: '+name)
            by_name[name].append({'time_s':frame['time_s'],'value':values[name]})
    for name,values in by_name.items():
        with (destination/(name+'.jsonl')).open('x') as stream:
            for value in values:
                stream.write(json.dumps(value,allow_nan=False)+'\n')
    return {'channels':len(by_name),'rows_per_channel':len(motion),
            'source_sha256':{name:sha(attempt/name) for name in
              ('native_samples.jsonl','video_frames.jsonl','road_geometry.json')}}


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError("Retain original finalization; use a fresh attempt")
    config=json.loads((attempt/'config.json').read_text())
    requested_count=config['duration_s']*config['rate_hz']
    count=round(requested_count)
    if abs(requested_count-count)>1e-6 or count<2:
        raise ValueError("Recording duration/rate does not yield an integral frame count")
    original=verify_original_joins(attempt,count)
    measured=measure_park(attempt)
    videos=[f'{name}.mkv' for name in ('overview','approach','intersection','parking')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError("Source camera frame count differs from delivered trace")
    actual={k:v for k,v in measured['value'].items() if k!='legal_verdict'}
    requested={'probe_a':'outside_intersection','probe_b':'within_intersection'}[config['case_suffix']]
    matched=actual['parking_relation']==requested
    saved_motion=rows(attempt/'native_samples.jsonl')
    endpoint=saved_motion[-1]['native_center_xy_m']
    target_x={'probe_a':-13.0,'probe_b':0.0}[config['case_suffix']]
    parked=math.dist(endpoint,[target_x,-1.75])<=.8 and saved_motion[-1]['speed_m_s']<=.05 and actual['parked_frames']>=40
    description=config['recording_description']
    derived=derive_channels(attempt,description)
    recording_evidence=[]
    for channel in description['channels']:
        name=channel['name'];reference='channels/'+name+'.jsonl'
        path=attempt/reference
        if not path.is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':name,'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        reference='context.json'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':context['name'],'unit':context['unit'],
                                   'reference':reference})
    result={'case_id':config['case_id'],'measured_values':actual,
      'target_checks':[{'target':'sampled sustained parking footprint relation to intersection',
        'requested':requested,'measured':actual['parking_relation'],
        'method':'original sampled Native full body versus surveyed intersection polygon',
        'tolerance':'50 ms sample uncertainty','matched':matched,
        'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl']}],
      'setup_confirmed':True,
      'behavior_attempted':True,'maneuver_completed':parked,
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['camera_and_native_surface_review_pending'] +
          ([] if matched and parked else
           ['tracking_or_completion_unconfirmed']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,
      'recording_evidence':recording_evidence,
      'realized_observables':{'intersection_parking_footprint':
          {'value':actual['max_intersection_body_overlap_m2'],'unit':'m2',
           'method':'maximum sampled parked full-body overlap with surveyed intersection polygon',
           'time_window':'original 24 s / 480 frame attempt',
           'statistic':'maximum sampled overlap','reference':'native_samples.jsonl'}},
      'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110454-450-1c-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'unexcepted_sustained_stop':measure_unexcepted_stop(attempt),
                            'intersection_parking_footprint':measured,
                            'parking_within_intersection_witness':measure_witness(attempt)},
            'original_joins':original,'video_frames':video_counts,
            'derived_channels':derived,
            'scope':'saved original Native sources and source video decode, not independent acceptance or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()

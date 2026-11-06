"""Saved-only LVMC C110454 parking finalization; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_park import measure


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


def measure_case_sources(attempt):
    attempt=Path(attempt)
    source=attempt/'native_parking_history.json'
    if not source.is_file():raise ValueError('Missing required source: native_parking_history.json')
    result=measure(source,sha(source))
    return {'value':result,'method':'measure_case_sources',
            'sources':{'native_parking_history.json':sha(source)}}


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
    measured=measure_case_sources(attempt)
    videos=[f'{name}.mkv' for name in ('overview','approach','intersection','parking')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError("Source camera frame count differs from delivered trace")
    actual={k:v for k,v in measured['value'].items() if k!='legal_verdict'}
    requested={'witness_1':'outside_15_ft','witness_2':'within_15_ft'}[config['case_suffix']]
    matched=actual['sampled_relation']==requested
    packet=json.loads((attempt/'native_parking_history.json').read_text())
    saved_motion=rows(attempt/'native_samples.jsonl')
    if len(packet['frames'])!=count or any(
        row['native_frame']!=sample['native_frame'] or
        row['body_xy_m']!=sample['native_body_xy_m'] or
        abs(row['speed_m_s']-sample['speed_m_s'])>1e-6
        for row,sample in zip(packet['frames'],saved_motion)):
        raise ValueError('Parking history differs from original Native samples')
    endpoint=saved_motion[-1]['native_center_xy_m']
    requested_stop={'witness_1':25.0,'witness_2':13.5}[config['case_suffix']]
    parked=math.dist(endpoint,[requested_stop,-5.25])<=.8 and saved_motion[-1]['speed_m_s']<=.3
    description=config['recording_description']
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
      'target_checks':[{'target':'sampled parked-body distance from intersection boundary',
        'requested':requested,'measured':actual['sampled_relation'],
        'method':'original sampled Native resting full body versus surveyed parking-side intersection boundary',
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
      'realized_observables':{'parked_footprint_distance_to_intersection':
          {'value':actual['nearest_parked_body_distance_m']/0.3048,'unit':'ft',
           'method':'nearest observed parked full-body sample to surveyed intersection boundary',
           'time_window':'original 24 s / 480 frame attempt',
           'statistic':'minimum sampled distance','reference':'native_parking_history.json'}},
      'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110454-lvmc-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'parked_body_distance_and_rest_interval':measured},
            'original_joins':original,'video_frames':video_counts,
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

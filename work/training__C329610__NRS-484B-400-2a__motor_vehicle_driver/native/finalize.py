"""Saved-only C329610 finalization proposal; no legal or acceptance verdict."""
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


def measure_approach(attempt):
    attempt=Path(attempt)
    result=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    return {'value':{'sampled_right_offset_m':result['center_to_centerline_right_offset_m'],
                     'full_body_right_half':result['full_body_within_right_half_on_sampled_approach'],
                     'destination_exit_observed':result['destination_exit_observed'],
                     'approach_window_s':result['approach_window_s'],
                     'entry_time_bracket_s':result['intersection_entry_time_bracket_s']},
            'method':'measure_approach',
            'sources':{name:sha(attempt/name) for name in ('native_samples.jsonl','road_geometry.json')}}


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
    measured=measure_approach(attempt)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError("Source camera frame count differs from delivered trace")
    actual=measured['value'];requested={'controlled_1':1.75,'controlled_2':5.25}[config['case_suffix']]
    mean=actual['sampled_right_offset_m']['mean'];matched=abs(mean-requested)<=.35
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
      'target_checks':[{'target':'approach centerline offset engineering target',
        'requested':requested,'measured':mean,'method':'original sampled Native body center vs surveyed centerline',
        'tolerance':.35,'matched':matched,
        'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl']}],
      'setup_confirmed':actual['full_body_right_half'],
      'behavior_attempted':True,'maneuver_completed':actual['destination_exit_observed'],
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['camera_and_native_surface_review_pending'] +
          ([] if matched and actual['destination_exit_observed'] else
           ['tracking_or_completion_unconfirmed']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,
      'recording_evidence':recording_evidence,
      'realized_observables':{'approach_centerline_right_offset_m':
          {'value':mean,'unit':'m','method':'sampled Native body center projection onto surveyed right normal',
           'time_window':'before first front-body intersection entry',
           'statistic':'mean','reference':'native_samples.jsonl',
           'sample_window_s':measured['value']['approach_window_s']}},
      'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c329610-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],'measurements':{'approach_placement_geometry':measured},
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

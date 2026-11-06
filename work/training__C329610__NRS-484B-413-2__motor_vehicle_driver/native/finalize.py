"""Saved-only C329610 signal finalization proposal; no legal or acceptance verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from signal_measure import measure


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


def measure_signal_distance(attempt, config):
    attempt=Path(attempt)
    geometry=json.loads((attempt/'road_geometry.json').read_text())
    if geometry.get('authored_map_sha256')!=config['native_request']['map_sha256'] or \
            not isinstance(geometry.get('native_map_sha256'),str) or len(geometry['native_map_sha256'])!=64:
        raise ValueError('Authored or Native map identity differs from exact request')
    source=attempt/'native_samples.jsonl'
    measured=measure(source,expected_sha256=sha(source),area=config['native_request']['area'])
    return {'value':measured['continuous_signal_distance_ft'],
            'method':'measure_signal_distance',
            'sources':{name:sha(attempt/name) for name in ('native_samples.jsonl','road_geometry.json')},
            'detail':measured}


def measure_weather_context(attempt, config):
    rows_source=rows(Path(attempt)/'native_samples.jsonl')
    weather={row['weather'] for row in rows_source}
    if weather!={config['native_request']['weather']}:
        raise ValueError('Weather source differs from exact request')
    return {'value':weather.pop(),'method':'measure_weather_context',
            'sources':{name:sha(Path(attempt)/name) for name in ('native_samples.jsonl','road_geometry.json')}}


def measure_other_area_coverage(attempt, config):
    source=rows(Path(attempt)/'native_samples.jsonl')
    if {row['area'] for row in source}!={'other'} or config['native_request']['area']!='other':
        raise ValueError('Other-area source context missing')
    return {'value':{'area':'other','sample_count':len(source)},
            'method':'measure_other_area_coverage',
            'sources':{name:sha(Path(attempt)/name) for name in ('native_samples.jsonl','road_geometry.json')}}


def measure_other_area_duplicate(attempt, config):
    item=measure_other_area_coverage(attempt,config)
    item['method']='measure_other_area_duplicate'
    return item


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    count=config['duration_s']*config['rate_hz']
    if count!=800:
        raise ValueError('Exact 800-frame capture contract changed')
    original=verify_original_joins(attempt,count)
    geometry=json.loads((attempt/'road_geometry.json').read_text())
    synthetic=geometry.get('provenance')=='synthetic_cpu_fixture'
    signal=measure_signal_distance(attempt,config)
    weather=measure_weather_context(attempt,config)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError('Source camera frame count differs from delivered trace')
    target=config['native_request']['target_signal_distance_ft']
    actual=signal['value']
    matched=abs(actual-target)<=.5
    description=config['recording_description']
    recording_evidence=[]
    for channel in description['channels']:
        reference='channels/'+channel['name']+'.jsonl'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':channel['name'],'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        reference='road_geometry.json'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':context['name'],'unit':context['unit'],'reference':reference})
    result={'case_id':config['case_id'],'measured_values':{'continuous_signal_distance_ft':actual,
             'weather':weather['value']},
      'target_checks':[{'target':'continuous sampled left signal distance before course change',
        'requested':target,'measured':actual,'method':'source-hashed Native signal and pose path',
        'tolerance':.5,'matched':matched,'physical_cause_confirmed':False,
        'cause_evidence':['native_samples.jsonl','road_geometry.json']}],
      'setup_confirmed':False,'behavior_attempted':not synthetic,'maneuver_completed':False,
      'termination_reason':'synthetic full-duration fixture processed' if synthetic else 'full original duration retained',
      'physical_failure_flags':(['synthetic_fixture_not_physical'] if synthetic else [])+
            ['area_classification_and_original_pixels_require_review']+
            ([] if matched else ['signal_distance_target_unconfirmed']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,'recording_evidence':recording_evidence,
      'realized_observables':{'continuous_signal_distance_ft':{'value':actual,'unit':'ft',
        'method':'sampled Native path with original indicator state','reference':'native_samples.jsonl',
        'time_window':'continuous preturn interval','statistic':'path length'}},
      'provenance_kind':'synthetic_cpu_fixture' if synthetic else 'native',
      'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    measurements={'continuous_signal_distance_ft':signal,'weather_context':weather}
    if config['native_request']['area']=='other':
        measurements['other_area_coverage']=measure_other_area_coverage(attempt,config)
        measurements['other_area_duplicate']=measure_other_area_duplicate(attempt,config)
    report={'format':'c329610-413-2-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],'measurements':measurements,
            'original_joins':original,'video_frames':video_counts,
            'scope':'saved source and decoded video; synthetic provenance retained when present; no independent acceptance or legal verdict'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()

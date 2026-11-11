"""Saved-only C110454 finalization proposal; no legal or acceptance verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_statutory import measure
from statutory_context import inspect as inspect_context


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
    source=attempt/'native_samples.jsonl';samples=rows(source)
    survey_path=attempt/'road_geometry.json'
    if not survey_path.is_file():raise ValueError('Missing required source: road_geometry.json')
    survey=json.loads(survey_path.read_text())
    config=json.loads((attempt/'config.json').read_text())
    frames=[row['native_frame'] for row in samples]
    context=inspect_context(attempt/'statutory_context.json',config['case_suffix'],frames,
                            survey_path,attempt/'road.xodr')
    result=measure(samples,source,sha(source),survey['approach_boundary_x_m'],
                   context['one_way'],context['zone_kind'])
    return {'value':result,'method':'measure_approach',
            'sources':{name:sha(attempt/name) for name in
              ('native_samples.jsonl','road_geometry.json','statutory_context.json')},
            'statutory_context':context}

def measure_left_side(attempt):
    approach=measure_approach(attempt)
    return {'value':approach['value']['left_driving_frames']>0,
            'method':'measure_left_side','sources':approach['sources']}


def measure_context(attempt):
    """Bind the one-way exception context to the retained Native survey."""
    approach=measure_approach(attempt)
    return {'value':approach['statutory_context'],'method':'measure_context',
            'sources':{name:sha(Path(attempt)/name) for name in
                       ('statutory_context.json','road_geometry.json')}}


def derive_channels(attempt,config,count):
    """Rebuild every observation from saved Native rows and surveyed sources."""
    samples=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    survey=json.loads((attempt/'road_geometry.json').read_text())
    statutory=json.loads((attempt/'statutory_context.json').read_text())
    if len(samples)!=count or len(mapping)!=count:
        raise ValueError('Original channel source counts differ')
    names={item['name'] for item in config['recording_description']['channels']}
    output={name:[] for name in names}
    for sample,frame in zip(samples,mapping):
        if sample['native_frame']!=frame['native_frame'] or abs(sample['time_s']-frame['time_s'])>1e-4:
            raise ValueError('Original channel frame/time join differs')
        body=sample['native_body_xy_m']
        values={
            'drv.approaching':{'native_center_xy_m':sample['native_center_xy_m'],
                               'native_forward_xy':sample['native_forward_xy']},
            'drv.in_intersection':{'body_intersects_surveyed_entry':
                                    max(point[0] for point in body)>=survey['intersection_entry_point_native_m'][0],
                                    'physical_intersection_status_verified':False},
            'st.intersection':survey,
            'st.railway_crossing':{'native_readback':survey['railroad_crossing_native_readback'],
                                   'object_id':survey['railroad_crossing_object_id'],
                                   'statutory_context':statutory['zone_kind']},
            'st.centre_line':survey['approach_centerline_point_native_m'],
            'rel.occupies':body,
            'kin.position':sample['native_center_xy_m'],
            'rel.centre_distance':{'body_front_x_m':max(point[0] for point in body),
                                   'zone_boundary_x_m':survey['approach_boundary_x_m']},
            'st.one_way_roadway':{'native_readback':survey['one_way_native_readback'],
                                   'road_directions_native':survey['road_directions_native']},
            'native_body_pose_control':sample,
            'camera_frame_join':frame}
        if set(values)!=names:
            raise ValueError('Declared channels differ from raw derivation')
        for name,value in values.items():
            output[name].append(json.dumps({'time_s':frame['time_s'],'value':value},allow_nan=False)+'\n')
    folder=attempt/'channels';folder.mkdir(exist_ok=True)
    for name,values in output.items():
        (folder/(name+'.jsonl')).write_text(''.join(values))


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
    capture=json.loads((attempt/'capture/manifest.json').read_text())
    synthetic=capture.get('synthetic_diagnostic') is True or capture.get('synthetic_fixture') is True
    if synthetic:
        trace=rows(attempt/'trace.jsonl');evidence=rows(attempt/'capture/evidence.jsonl')
        motion=rows(attempt/'native_samples.jsonl')
        if not all(row.get('synthetic_diagnostic') is True and
                   row.get('speed_provenance')=='synthetic_native_sample'
                   for source in (trace,motion) for row in source) or not all(
                       row.get('synthetic_diagnostic') is True and
                       row.get('ego',{}).get('speed_provenance')=='synthetic_native_sample'
                       for row in evidence):
            raise ValueError('Synthetic speed must retain diagnostic provenance')
    measured=measure_approach(attempt)
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    video_counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in video_counts.values()):
        raise ValueError("Source camera frame count differs from delivered trace")
    actual={k:v for k,v in measured['value'].items() if k!='legal_verdict'}
    requested={'rail_reference':'outside_100_ft','rail_contrast':'within_100_ft',
               'oneway_absent':'within_100_ft','oneway_present':'within_100_ft'}[config['case_suffix']]
    matched=actual['sampled_relation']==requested
    saved_motion=rows(attempt/'native_samples.jsonl')
    endpoint=saved_motion[-1]['native_center_xy_m']
    parked=math.dist(endpoint,[20,-5.25])<=.8 and saved_motion[-1]['speed_m_s']<=.3
    description=config['recording_description']
    derive_channels(attempt,config,count)
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
      'target_checks':[{'target':'sampled left-side '+measured['statutory_context']['zone_kind']+' approach relation',
        'requested':requested,'measured':actual['sampled_relation'],
        'method':'original sampled Native full body versus surveyed roadway centerline and statutory zone boundary',
        'tolerance':'50 ms sample uncertainty','matched':matched,
        'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl']}],
      'setup_confirmed':not synthetic,
      'behavior_attempted':not synthetic,'maneuver_completed':not synthetic and parked,
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['camera_and_native_surface_review_pending'] +
          ([] if matched and parked else
           ['tracking_or_completion_unconfirmed']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,
      'recording_evidence':recording_evidence,
      'realized_observables':{'left_side_entry_distance_to_zone':
          {'value':actual['nearest_body_front_to_zone_m']/0.3048,'unit':'ft',
           'method':'nearest observed full-body left-side sample front to surveyed entry boundary',
           'time_window':'original 24 s / 480 frame attempt',
           'statistic':'minimum sampled distance','reference':'native_samples.jsonl'}},
      'provenance_kind':'synthetic_local_diagnostic' if synthetic else 'native',
      'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c110454-saved-analysis-v1','case_id':config['case_id'],
            'candidate_id':config['candidate_id'],
            'measurements':{'left_side_driving':measure_left_side(attempt),
                            'statutory_approach_relation':measured,
                            'statutory_context':measure_context(attempt)},
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

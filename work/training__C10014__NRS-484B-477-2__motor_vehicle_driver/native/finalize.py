"""Saved-only original-source alley entrance measurement; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_entrance import measure


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_original_joins(attempt,count):
    attempt=Path(attempt)
    trace=rows(attempt/'trace.jsonl')
    evidence=rows(attempt/'capture/evidence.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    motion=rows(attempt/'native_samples.jsonl')
    body=rows(attempt/'body_history.jsonl')
    if not all(len(source)==count for source in (trace,evidence,mapping,motion,body)):
        raise ValueError('Original trace/evidence/body/frame counts differ')
    prior_frame=-1;prior_time=-math.inf
    for index,(t,e,m,n,b) in enumerate(zip(trace,evidence,mapping,motion,body)):
        frame=m.get('native_frame');time=m.get('time_s')
        if (type(frame) is not int or type(time) not in (float,int) or
            frame<=prior_frame or time<=prior_time or m.get('video_frame')!=index or
            m.get('carla_frame')!=frame):
            raise ValueError('Original frame/time mapping invalid')
        prior_frame=frame;prior_time=time
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),
                                        n.get('native_frame'),b.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(item)-time)>1e-4 for item in
               (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in n['native_body_xy_m']}
        history={(round(v[0],5),round(v[1],5)) for v in b['body_vertices_m']}
        if len(captured)!=4 or captured!=measured or measured!=history:
            raise ValueError('Original full body differs from saved measurement')
    manifest=json.loads((attempt/'capture/manifest.json').read_text())
    if not manifest.get('extraction_confirmed') or manifest.get('frames')!=count:
        raise ValueError('Original capture extraction incomplete')
    names=('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
           'native_samples.jsonl','body_history.jsonl','capture/manifest.json')
    return {'frames':count,'first_frame':mapping[0]['native_frame'],
            'last_frame':mapping[-1]['native_frame'],
            'first_time_s':mapping[0]['time_s'],'last_time_s':mapping[-1]['time_s'],
            'source_hashes':{name:sha(attempt/name) for name in names}}


def video_frames(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
       '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
       text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name+' '+result.stderr[-300:])
    return int(result.stdout.strip())


def entrance_overlap_observation(attempt):
    attempt=Path(attempt)
    result=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    return {'method':'entrance_overlap_observation',
            'value':{'max_entrance_overlap_m':result['max_entrance_overlap_m'],
                     'mean_entrance_overlap_m':result['mean_entrance_overlap_m']},
            'sources':result['source_sha256']}


def derive_channels(attempt,config,count):
    """Rebuild every declared channel from retained raw rows and map context."""
    attempt=Path(attempt)
    motion=rows(attempt/'native_samples.jsonl')
    mapping=rows(attempt/'video_frames.jsonl')
    if len(motion)!=count or len(mapping)!=count:
        raise ValueError('Raw channel source counts differ')
    geometry=json.loads((attempt/'road_geometry.json').read_text())
    expected={'st.alley','st.driveway_or_alley_entrance','rel.occupies',
              'kin.extent','kin.position','ego_speed','native_body_pose_control',
              'camera_frame_join'}
    declared={item['name'] for item in config['recording_description']['channels']}
    if declared!=expected:
        raise ValueError('Declared channels differ from raw derivation')
    output={name:[] for name in expected}
    for sample,frame in zip(motion,mapping):
        if sample['native_frame']!=frame['native_frame'] or abs(sample['time_s']-frame['time_s'])>1e-4:
            raise ValueError('Channel source frame/time join differs')
        values={'st.alley':{'road_id':sample['native_road_id'],
                            'lane_id':sample['native_lane_id'],
                            'alley_road_id':geometry['alley_native_road_id'],
                            'alley_lane_id':geometry['alley_native_lane_id']},
                'st.driveway_or_alley_entrance':geometry,
                'rel.occupies':{'body_xy_m':sample['native_body_xy_m'],
                                'road_id':sample['native_road_id'],
                                'lane_id':sample['native_lane_id']},
                'kin.extent':{'body_xy_m':sample['native_body_xy_m']},
                'kin.position':sample['native_center_xy_m'],
                'ego_speed':sample['speed_mps'],
                'native_body_pose_control':sample,
                'camera_frame_join':{key:frame[key] for key in
                                     ('video_frame','native_frame','carla_frame','time_s')}}
        for name,value in values.items():
            output[name].append(json.dumps({'time_s':sample['time_s'],'value':value},allow_nan=False)+'\n')
    directory=attempt/'channels';directory.mkdir(exist_ok=True)
    for name,records in output.items():
        (directory/(name+'.jsonl')).write_text(''.join(records))


def alley_stop_context(attempt):
    attempt=Path(attempt)
    result=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    return {'method':'alley_stop_context',
            'value':{'first_frame':result['stop_first_frame'],
                     'last_frame':result['stop_last_frame'],
                     'duration_s':result['stop_duration_s'],
                     'native_design_verified':result['native_design_verified'],
                     'legal_blocking_verdict_claimed':False},
            'sources':result['source_sha256']}


def physical_checks(observed,matched,synthetic):
    """Describe measured motion separately from independent access review."""
    sources=observed['source_sha256']
    interval=[{'first_frame':observed['stop_first_frame'],
               'last_frame':observed['stop_last_frame']}]
    common={'sources':sources,'intervals':interval,
            'legal_verdict_claimed':False,'physical_causation_claimed':False}
    def check(status,method,details):
        return {**common,'status':status,'method':method,'details':details}
    observed_motion=not synthetic
    return {
      'setup':check('unverified','Native lane survey; independent property-access designation pending',
                    {'native_design_verified':observed['native_design_verified']}),
      'target':check('unverified' if synthetic else ('met' if matched else 'not_met'),
                     'original sampled stationary body overlap against authored geometric target',
                     {'max_entrance_overlap_m':observed['max_entrance_overlap_m'],
                      'matched':matched,'engineering_target_not_legal_threshold':True}),
      'maneuver':check('unverified' if synthetic else ('met' if matched else 'not_met'),
                       'original sampled alley stop lasting at least two seconds with measured body overlap',
                       {'stop_duration_s':observed['stop_duration_s'],
                        'max_entrance_overlap_m':observed['max_entrance_overlap_m'],
                        'matched':matched,'native_motion_observed':observed_motion}),
      'attempt':check('unverified' if synthetic else 'met',
                      'full source-joined 480-frame capture; independent review remains separate',
                      {'original_frames':observed['original_frames']})}


def finalize(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads((attempt/'config.json').read_text())
    count=round(config['duration_s']*config['rate_hz'])
    if count!=480:raise ValueError('Expected original 480-frame attempt')
    original=verify_original_joins(attempt,count)
    derive_channels(attempt,config,count)
    observed=measure(attempt/'native_samples.jsonl',attempt/'road_geometry.json')
    measurements={'entrance_overlap_observation':entrance_overlap_observation(attempt),
                  'alley_stop_context':alley_stop_context(attempt)}
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if any(frames!=count for frames in counts.values()):
        raise ValueError('Source camera frame count differs from original trace')
    description=config['recording_description'];recording_evidence=[]
    for channel in description['channels']:
        name=channel['name'];reference='channels/'+name+'.jsonl'
        if not (attempt/reference).is_file():raise ValueError('Missing required source: '+reference)
        recording_evidence.append({'name':name,'unit':channel['unit'],'reference':reference})
    for context in description['context_inputs']:
        if not (attempt/'context.json').is_file():raise ValueError('Missing required source: context.json')
        recording_evidence.append({'name':context['name'],'unit':context['unit'],
                                   'reference':'context.json'})
    requested={'reference':0.0,'contrast':5.2}[config['case_suffix']]
    overlap=observed['max_entrance_overlap_m']
    matched=abs(overlap-requested)<=.25
    synthetic=json.loads((attempt/'capture/manifest.json').read_text()).get('synthetic_diagnostic') is True
    if synthetic:
        evidence=rows(attempt/'capture/evidence.jsonl')
        trace=rows(attempt/'trace.jsonl')
        motion=rows(attempt/'native_samples.jsonl')
        if not all(row.get('synthetic_diagnostic') is True and
                   row.get('ego',{}).get('speed_provenance')=='synthetic_native_sample'
                   for row in evidence) or not all(
                       row.get('synthetic_diagnostic') is True and
                       row.get('speed_provenance')=='synthetic_native_sample'
                       for source in (trace,motion) for row in source):
            raise ValueError('Synthetic speed must retain diagnostic provenance')
    result={'case_id':config['case_id'],
      'measured_values':{'max_entrance_overlap_m':overlap,
                         'stop_duration_s':observed['stop_duration_s']},
      'target_checks':[{'target':'stationary alley vehicle at requested geometric entrance overlap',
        'requested':requested,'measured':overlap,
        'method':'original Native body/road/lane/speed and surveyed entrance corridor',
        'tolerance':'absolute overlap difference <= 0.25 m, with at least 2 s sampled stop',
        'matched':matched,'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl']}],
      'setup_confirmed':False,
      'behavior_attempted':not synthetic,'maneuver_completed':not synthetic and matched,
      'physical_checks':physical_checks(observed,matched,synthetic),
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['alley_access_design_and_pixels_unverified']+
          ([] if matched else ['requested_stop_overlap_not_measured']),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':description,'recording_evidence':recording_evidence,
      'realized_observables':{'sampled_stopped_entrance_overlap':{
          'value':overlap,'unit':'m','method':'maximum original sampled stationary body projection inside entrance corridor',
          'time_window':'observed stationary alley interval','statistic':'maximum',
          'reference':'native_samples.jsonl',
          'sample_window_s':[observed['stop_first_frame']/20,observed['stop_last_frame']/20]}},
      'provenance_kind':('synthetic_local_diagnostic' if synthetic else 'native'),
      'accepted':False,'legal_verdict_claimed':False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report={'format':'c10014-alley-entrance-saved-analysis-v1',
      'case_id':config['case_id'],'candidate_id':config['candidate_id'],
      'measurements':measurements,'original_joins':original,'video_frames':counts,
      'scope':'saved original source diagnostic; physical access and legal blocking judgment unverified'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    return report


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))


if __name__=='__main__':main()

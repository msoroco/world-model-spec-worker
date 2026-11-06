"""Draft saved-source measurements; no physical or legal acceptance verdict."""
import hashlib
import json
import math
import subprocess
from pathlib import Path

from measure_after_turn import measure


def _required(folder, name):
    path=Path(folder)/name
    if not path.is_file(): raise ValueError('Missing required source: '+name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def activation_context(folder):
    geometry=json.loads(_required(folder,'road_geometry.json').read_text())
    return {'authored_center_lane_bounds_m':geometry['center_turn_lane_native_xy_bounds_m'],
            'native_center_lane_design_verified':geometry.get('native_center_lane_design_verified') is True,
            'authored_map_sha256':geometry['authored_map_sha256']}


def distance_after_turn(folder):
    samples=_required(folder,'native_samples.jsonl')
    geometry=_required(folder,'road_geometry.json')
    return measure(samples,geometry)


def turn_merge_scope(folder):
    measured=distance_after_turn(folder)
    return {'left_turn_road_transition_frame_bracket':measured['left_turn_road_transition_frame_bracket'],
            'turn_completion_frame_bracket':measured['turn_completion_frame_bracket'],
            'merge_onset_frame_bracket':measured['merge_onset_frame_bracket'],
            'full_merge_native_frame':measured['full_merge_native_frame']}


def analysis_report(folder,contract=None):
    folder=Path(folder)
    if contract is None:
        contract={'case_id':json.loads(_required(folder,'config.json').read_text())['case_id'],
                  'requirements':[
                      {'output_key':'center_lane_activation_context','method':'activation_context',
                       'inputs':['road_geometry.json']},
                      {'output_key':'after_left_turn_distance_interval','method':'distance_after_turn',
                       'inputs':['native_samples.jsonl','road_geometry.json']},
                      {'output_key':'turn_to_merge_scope','method':'turn_merge_scope',
                       'inputs':['native_samples.jsonl','road_geometry.json']}]}
    methods={'activation_context':activation_context,
             'distance_after_turn':distance_after_turn,
             'turn_merge_scope':turn_merge_scope}
    values={}
    for row in contract['requirements']:
        inputs={name:_sha(_required(folder,name)) for name in row['inputs']}
        values[row['output_key']]={'method':row['method'],
                                   'value':methods[row['method']](folder),
                                   'sources':inputs}
    return {'format':'draft-saved-analysis-v1','case_id':contract['case_id'],
            'draft_only':True,'selected':False,'measurements':values}


def _rows(folder,name):
    return [json.loads(line) for line in _required(folder,name).read_text().splitlines() if line.strip()]


def verify_original_joins(folder,count):
    names=('trace.jsonl','capture/evidence.jsonl','video_frames.jsonl',
           'native_samples.jsonl','body_history.jsonl','capture/native/frames.jsonl')
    trace,evidence,mapping,motion,body,native_frames=(_rows(folder,name) for name in names)
    if any(len(source)!=count for source in (trace,evidence,mapping,motion,body,native_frames)):
        raise ValueError('Original trace/evidence/body/frame counts differ')
    previous_frame=-1;previous_time=-math.inf
    for index,(t,e,m,n,b,f) in enumerate(zip(trace,evidence,mapping,motion,body,native_frames)):
        frame=m.get('native_frame');time=float(m['time_s'])
        if not isinstance(frame,int) or frame<=previous_frame or time<=previous_time or m['video_frame']!=index or m.get('carla_frame')!=frame:
            raise ValueError('Original frame/time mapping invalid')
        previous_frame=frame;previous_time=time
        if any(item!=frame for item in (t.get('frame'),e.get('original_frame'),n.get('native_frame'),b.get('frame'),f.get('frame'))):
            raise ValueError('Original Native frame join differs')
        if any(abs(float(item)-time)>1e-4 for item in
               (t['time_s'],e['recording_time_s'],n['time_s'],b['time_s'],f['time_s'])):
            raise ValueError('Original Native timestamp join differs')
        captured={(round(v[0],5),round(v[1],5)) for v in e['ego']['body_vertices_m']}
        measured={(round(v[0],5),round(v[1],5)) for v in n['native_body_xy_m']}
        historical={(round(v[0],5),round(v[1],5)) for v in b['body_vertices_m']}
        if captured!=measured or measured!=historical or len(measured)!=4:
            raise ValueError('Original full body differs from saved measurement')
    meta=json.loads(_required(folder,'capture/manifest.json').read_text())
    if not meta.get('extraction_confirmed') or meta.get('frames')!=count:
        raise ValueError('Original capture extraction incomplete')
    return {'frames':count,'first_frame':mapping[0]['native_frame'],
            'last_frame':mapping[-1]['native_frame'],
            'source_hashes':{name:_sha(Path(folder)/name) for name in names}}


def video_frames(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    result=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
        '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
        text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: '+path.name)
    return int(result.stdout.strip())


def finalize(attempt,output):
    from worker_exchange.native_output import validate_result
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config=json.loads(_required(attempt,'config.json').read_text())
    count=config['duration_s']*config['rate_hz']
    if type(count) is not int or count<2:
        raise ValueError('Recording duration/rate invalid')
    joins=verify_original_joins(attempt,count)
    report=analysis_report(attempt)
    relation=report['measurements']['after_left_turn_distance_interval']['value']['threshold_relation']
    scope=report['measurements']['turn_to_merge_scope']['value']
    context=report['measurements']['center_lane_activation_context']['value']
    videos=[f'{name}.mkv' for name in ('overview','approach','reference_corner','driver_reference')]
    counts={name:video_frames(attempt/name) for name in videos}
    if set(counts.values())!={count}:raise ValueError('Source camera frame count differs')
    requested={'below_50_ft':'within_50_feet','at_50_ft':'unresolved_at_50_feet',
               'above_50_ft':'exceeds_50_feet'}[config['case_suffix']]
    recording_evidence=[]
    for channel in config['recording_description']['channels']:
        name=channel['name'];ref='channels/'+name+'.jsonl';_required(attempt,ref)
        recording_evidence.append({'name':name,'unit':channel['unit'],'reference':ref})
    for item in config['recording_description']['context_inputs']:
        _required(attempt,'context.json')
        recording_evidence.append({'name':item['name'],'unit':item['unit'],'reference':'context.json'})
    measured=report['measurements']['after_left_turn_distance_interval']['value']
    result={'case_id':config['case_id'],'measured_values':measured,
      'target_checks':[{'target':'full-body after-turn center-lane distance and completed merge',
        'requested':requested,'measured':relation,
        'method':'original Native connector transition, full-body center-lane completion, through-lane contact and complete merge',
        'tolerance':'source-frame bracket; unresolved boundary is unmatched',
        'matched':relation==requested and relation!='unresolved_at_50_feet',
        'physical_cause_confirmed':False,
        'cause_evidence':['road_geometry.json','native_samples.jsonl','trace.jsonl']}],
      'setup_confirmed':context['native_center_lane_design_verified'],
      'behavior_attempted':True,'maneuver_completed':True,
      'termination_reason':'full original duration retained',
      'physical_failure_flags':['center_turn_lane_design_and_pixels_unverified']+
         (['distance_threshold_unresolved'] if relation=='unresolved_at_50_feet' else []),
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl',
      'recording_description':config['recording_description'],
      'recording_evidence':recording_evidence,
      'realized_observables':{'after_turn_center_lane_distance':{
          'value':measured['sampled_distance_m'],'unit':'m',
          'method':'original sampled path between full-body turn completion and first through-lane body contact',
          'time_window':'turn completion to merge onset','statistic':'sampled cumulative path',
          'reference':'native_samples.jsonl','interval_m':measured['distance_interval_m'],
          'turn_completion_frame_bracket':scope['turn_completion_frame_bracket'],
          'merge_onset_frame_bracket':scope['merge_onset_frame_bracket']}},
      'provenance_kind':'native','accepted':False,'legal_verdict_claimed':False}
    validate_result(result)
    report.update(format='c394300-3c-saved-after-turn-analysis-v1',
                  candidate_id=config['candidate_id'],original_joins=joins,
                  video_frames=counts,
                  scope='saved original Native sources and source-video decode; physical designation and legal verdict unverified')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output)))

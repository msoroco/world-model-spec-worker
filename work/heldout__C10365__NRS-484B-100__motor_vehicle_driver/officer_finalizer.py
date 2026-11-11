"""Saved-only, source-bound officer-direction and observed-response finalizer."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
from officer_response import measure
from officer_native_runner import check_config

def source(root,name):
    path=Path(root)/name
    if not path.is_file() or not path.read_bytes():raise ValueError('Missing required source: '+name)
    return path

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def measure_officer(context,direction,motion,command):
    """Named exact-contract source measurement without a legal verdict."""
    return measure(context,direction,motion,expected_actor='motor_vehicle_driver',expected_command=command)

def analyze(root):
    root=Path(root);cfg=json.loads(source(root,'config.json').read_text());command,_=check_config(cfg)
    context=source(root,'officer_context.json');direction=source(root,'officer_direction.json');motion=source(root,'subject_motion.json')
    observed=measure_officer(context,direction,motion,command)
    mapping=rows(source(root,'video_frames.jsonl'));trace=rows(source(root,'trace.jsonl'))
    history=rows(source(root,'subject_motion_history.jsonl'))
    if len(mapping)<3 or len(mapping)!=len(trace) or len(trace)!=len(history):
        raise ValueError('Original officer frame-map, trace and motion lengths differ')
    for index,(fm,t,h) in enumerate(zip(mapping,trace,history)):
        if (fm.get('video_frame')!=index or fm.get('carla_frame')!=t.get('frame') or t.get('frame')!=h.get('frame')
                or fm.get('time_s')!=t.get('time_s') or t.get('time_s')!=h.get('time_s')
                or h.get('subject_id')!=observed['subject_id']):
            raise ValueError('Original officer frame join differs')
    if observed['indication_frame'] not in {h['frame'] for h in history}:
        raise ValueError('Timed original indication absent from frame map')
    joined={h['frame']:h for h in history}
    raw_motion=json.loads(motion.read_text())['frames']
    if raw_motion!=history:raise ValueError('Original officer motion JSON and JSONL differ')
    channels={
        'subject_speed_mps':[(h['frame'],h['time_s'],h['speed_mps']) for h in history],
        'officer_direction':[(h['frame'],h['time_s'],1 if h['frame']>=observed['indication_frame'] else 0) for h in history],
    }
    for name,data in channels.items():
        (root/(name+'.jsonl')).write_text(''.join(json.dumps({'frame':f,'time_s':t,'value':v})+'\n' for f,t,v in data))
    sources={name:sha(source(root,name)) for name in ('officer_context.json','officer_direction.json','subject_motion.json','subject_motion_history.jsonl','video_frames.jsonl','trace.jsonl')}
    return {'format':'worker-analysis-report','case_id':cfg['selected_case_id'],
            'measurements':{'officer_response':{'method':'measure_officer','value':observed,'sources':sources}},
            'legal_acceptance_claimed':False,'physical_acceptance_claimed':False}

def result(root,report):
    root=Path(root);cfg=json.loads((root/'config.json').read_text());observed=report['measurements']['officer_response']['value']
    contexts=[]
    for name,reference in (('officer_context','officer_context.json'),
                           ('officer_direction_context','officer_direction.json'),
                           ('subject_motion_context','subject_motion.json'),
                           ('subject_motion_history','subject_motion_history.jsonl')):
        original=root/reference
        value=rows(original) if original.suffix=='.jsonl' else json.loads(original.read_text())
        derived=root/(name+'-recorded.json')
        if derived.exists():raise ValueError('Retain prior derived officer context')
        derived.write_text(json.dumps({name:value})+'\n')
        contexts.append({'name':name,'unit':'structured record',
                         'reference':derived.name,'sha256':sha(derived)})
    return {'case_id':report['case_id'],'measured_values':{'officer_response':observed},
            'target_checks':[{'target':'timed officer indication and observable response','requested':cfg['case']['intended_observed_response'],
                              'measured':observed['observed_response'],'method':'source-bound indication and post-indication original motion',
                              'tolerance':None,'matched':observed['observed_response']==cfg['case']['intended_observed_response'],
                              'physical_cause_confirmed':False,'cause_evidence':'Original gesture and subject motion; lawful duty and willfulness need independent review'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'Saved source measurement complete; physical and legal outcome unverified',
            'physical_failure_flags':{'gesture_visibility_unverified':True,'officer_authority_unverified':True},
            'trace_reference':'trace.jsonl','video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':cfg['case']['recording_description'],
            'recording_evidence':[
                *[{'name':name,'unit':unit,'reference':name+'.jsonl','sha256':sha(root/(name+'.jsonl'))}
                  for name,unit in (('subject_speed_mps','m/s'),('officer_direction','boolean'))],
                *contexts],
            'realized_observables':{'subject_speed_mps':{'unit':'m/s','method':'original subject velocity sampled after indication',
                                  'time_window':'post-indication original frames','statistic':'min',
                                  'reference':'subject_speed_mps.jsonl','value':observed['min_post_speed_mps'],
                                  'sample_window_s':[0,(observed['last_motion_frame']-observed['indication_frame'])/20]},
                                    'officer_direction':{'unit':'boolean','method':'original walker pose activation at indication frame',
                                  'time_window':'all original frames','statistic':'event','reference':'officer_direction.jsonl',
                                  'value':1,'sample_window_s':[0,(observed['last_motion_frame']-observed['first_motion_frame'])/20]}},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True);a=parser.parse_args()
    report=analyze(a.attempt);out=Path(a.output)
    if out.exists():raise ValueError('Retain prior analysis report')
    out.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(a.attempt,result(a.attempt,report))
if __name__=='__main__':main()

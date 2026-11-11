"""Saved-source finalization for NRS 484B.623(1); no legal classification."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from slow_speed import measure

CAMERAS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def _required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    if not raw:
        raise ValueError('Empty required source: ' + name)
    return path, sha256(raw).hexdigest()


def _rows(root, name):
    path, digest = _required(root, name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty required source: ' + name)
    return rows, digest


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config_path, config_hash = _required(root,'config.json')
    context_path, context_hash = _required(root,'slow_context.json')
    config = json.loads(config_path.read_text())
    context = json.loads(context_path.read_text())
    if config.get('law_id') != 'NRS-484B-623-1' or config.get('cell_id') != 'C136529' or config.get('actor') != 'motor_vehicle_driver':
        raise ValueError('wrong slow-speed law/cell/actor identity')
    branch = context.get('case_branch')
    if branch not in ('flowing_reference','slow_with_following_traffic',
                      'slow_for_obstruction','slow_under_control'):
        raise ValueError('missing exact case branch context')
    if config.get('selected_case_id','').split('__')[-1] != branch:
        raise ValueError('selected exact case differs from context')
    frames, frame_hash = _rows(root,'video_frames.jsonl')
    trace, trace_hash = _rows(root,'trace.jsonl')
    actors, actor_hash = _rows(root,'participant_state.jsonl')
    props, prop_hash = _rows(root,'prop_state.jsonl')
    if not (len(frames)==len(trace)==len(actors)==len(props)):
        raise ValueError('source frame count differs')
    samples=[];last=None
    for index,(f,t,a,p) in enumerate(zip(frames,trace,actors,props)):
        ident=(f.get('carla_frame'),f.get('time_s'))
        if (f.get('video_frame')!=index or type(ident[0]) is not int
                or (last is not None and (ident[0]<=last[0] or ident[1]<=last[1]))):
            raise ValueError('original frame map invalid')
        if any((row.get('frame'),row.get('time_s'))!=ident for row in (t,a,p)):
            raise ValueError('original frame/time join differs')
        last=ident
        sample=dict(a)
        sample['obstruction_visible']=p.get('obstruction_visible')
        sample['control_visible']=p.get('control_visible')
        sample['source']='participant_state.jsonl'
        samples.append(sample)
    observations=measure(samples)
    if branch=='slow_for_obstruction' and not all(p.get('obstruction_present') is True and len((p.get('obstruction_geometry') or {}).get('vertices_xyz',[]))>=4 for p in props):
        raise ValueError('physical obstruction missing from retained prop source')
    if branch=='slow_under_control' and not all(p.get('control_present') is True and len((p.get('control_geometry') or {}).get('vertices_xyz',[]))>=4 for p in props):
        raise ValueError('physical control missing from retained prop source')
    if branch=='slow_under_control' and not context.get('regulatory_source'):
        raise ValueError('regulatory premise needs a source')
    sources={'config.json':config_hash,'slow_context.json':context_hash,
             'video_frames.jsonl':frame_hash,'trace.jsonl':trace_hash,
             'participant_state.jsonl':actor_hash,'prop_state.jsonl':prop_hash}
    if write_channels:
        for name,key,unit in (('ego_speed_mps','ego_speed_mps','m/s'),
                              ('follower_speed_mps','follower_speed_mps','m/s'),
                              ('follower_gap_m','follower_gap_m','m')):
            (root/(name+'.jsonl')).write_text(''.join(json.dumps({'time_s':row['time_s'],
                       'value':row[key],'frame':f['carla_frame']})+'\n'
                       for row,f in zip(observations['samples'],frames)))
    return {'format':'worker-analysis-report','case_id':config['selected_case_id'],
            'measurements':{'slow_speed_observation':{'method':'original 20 Hz Native participant and prop join',
                        'value':observations,'sources':sources}},
            'limitations':['Normal and reasonable movement, necessity and regulatory validity remain subject to source and physical review.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def build_result(attempt, report):
    root=Path(attempt)
    config=json.loads((root/'config.json').read_text())
    description=config.get('case',{}).get('recording_description')
    if not isinstance(description,dict):
        raise ValueError('Missing selected recording description')
    observed=report['measurements']['slow_speed_observation']['value']
    channel_specs=(('ego_speed_mps','m/s','mean_ego_speed_mps'),
                   ('follower_speed_mps','m/s','mean_follower_speed_mps'),
                   ('follower_gap_m','m','minimum_follower_gap_m'))
    evidence=[];realized={}
    for name,unit,stat in channel_specs:
        path=root/(name+'.jsonl')
        if not path.is_file():
            raise ValueError('Missing derived channel from retained original source: '+name)
        evidence.append({'name':name,'unit':unit,'reference':path.name,
                         'sha256':sha256(path.read_bytes()).hexdigest()})
        realized[name]={'unit':unit,'method':'original synchronized 20 Hz Native participant positions and velocity',
                        'time_window':'all original frames','statistic':'minimum' if name=='follower_gap_m' else 'mean',
                        'reference':path.name,'value':observed[stat],
                        'sample_window_s':[observed['samples'][0]['time_s'],observed['samples'][-1]['time_s']]}
    return {'case_id':report['case_id'],'measured_values':{'slow_speed_observation':observed},
            'target_checks':[{'target':'descriptive speed and traffic interaction',
                  'requested':config.get('ego_target_mps'),'measured':observed['mean_ego_speed_mps'],
                  'method':'mean measured ego speed over original frames','tolerance':None,
                  'matched':False,'physical_cause_confirmed':False,
                  'cause_evidence':'Original participant and prop sources; actual traffic impedance and exceptions require review'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'Saved source measurement complete; physical outcome unverified',
            'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl',
            'video_references':list(CAMERAS),'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':description,'recording_evidence':evidence,
            'realized_observables':realized,'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=analyze(args.attempt)
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior analysis report; choose fresh output')
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))

if __name__=='__main__': main()

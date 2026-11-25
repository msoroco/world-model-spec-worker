"""Finalize original driving sources; attention and legal outcome remain for review."""
import argparse
import hashlib
import json
from pathlib import Path

from attention_observation import measure

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native-ego-frames.jsonl', 'video_frames.jsonl', 'native-driving-context.json')


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_operation_window(observation):
    speeds = observation['measurements']['ego_speed']
    return bool(observation['sample_count'] == 600 and len(speeds) == 600 and
                sum(v > 0.2 for v in speeds) >= 300 and
                set(observation['camera_decode']) == set(VIEWS))


def measure_continuous_window(observation):
    samples=observation['measurements']['ego_pose']
    return bool(len(samples)==600 and all(row['frame']==i for i,row in enumerate(samples)))

def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    config = json.loads((attempt/'config.json').read_text())
    case_id = config['case_id']
    if not case_id.endswith(('__reference', '__contrast')):
        raise ValueError('Wrong exact attention case')
    for name in (*SOURCES, 'trace.jsonl', *[v+'.mkv' for v in VIEWS]):
        sha(attempt/name)
    observation = measure(attempt)
    matched = measure_operation_window(observation)
    continuous = measure_continuous_window(observation)
    frame_map = [json.loads(line) for line in (attempt/'video_frames.jsonl').read_text().splitlines()]
    values = observation['measurements']
    description = config['recording_description']
    channel_values = {
        'ego_pose': values['ego_pose'],
        'ego_speed': values['ego_speed'],
        'ego_yaw_rate': values['ego_yaw_rate'],
        'ego_acceleration': values['ego_acceleration'],
        'driver_attention_to_operation': [None]*600,
        'driver_reference_video': ['driver_reference.mkv']*600,
    }
    evidence = []
    (attempt/'channels').mkdir(exist_ok=True)
    for channel in description['channels']:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('Unknown recording channel: '+name)
        ref = 'channels/'+name+'.jsonl'
        with (attempt/ref).open('x') as stream:
            for frame, value in zip(frame_map, channel_values[name]):
                stream.write(json.dumps({'time_s':frame['time_s'],'value':value}, allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],'reference':ref})
    for context in description.get('context_inputs', []):
        evidence.append({'name':context['name'],'unit':context['unit'],
                         'reference':'native-driving-context.json'})
    result = {
        'case_id':case_id,
        'measured_values':{'driving_cues':{'speed_min_mps':min(values['ego_speed']),
                                         'speed_max_mps':max(values['ego_speed']),
                                         'attention_review_required':True}},
        'target_checks':[{'target':'complete 30-second original vehicle-operation source',
                          'requested':True,'measured':matched,
                          'method':'600-frame original Native motion and four-camera source join',
                          'tolerance':0,'matched':matched,
                          'physical_cause_confirmed':False,
                          'cause_evidence':list(SOURCES)}],
        'setup_confirmed':matched,'behavior_attempted':matched,
        'maneuver_completed':matched,
        'termination_reason':'saved original 600-frame vehicle-operation source analyzed',
        'physical_failure_flags':[] if matched else ['incomplete_operation_source'],
        'trace_reference':'trace.jsonl',
        'video_references':[v+'.mkv' for v in VIEWS],
        'video_frame_map_reference':'video_frames.jsonl',
        'recording_description':description,'recording_evidence':evidence,
        'realized_observables':{},'accepted':False,
        'provenance_kind':('synthetic_fixture' if observation['source_kind']=='synthetic_native_sample' else 'native'),
        'physical_acceptance_claimed':False,'legal_verdict_claimed':False,
        'driver_attention_to_operation':None,
        'attention_review_required':True,
    }
    report={'format':'worker-analysis-report','case_id':case_id,
            'measurements':{'complete_operation_window':{
                'value':matched,'method':'measure_operation_window',
                'sources':{name:sha(attempt/name) for name in SOURCES}},
                            'continuous_operation_source':{
                'value':continuous,'method':'measure_continuous_window',
                'sources':{name:sha(attempt/name) for name in SOURCES}}},
            'measurement_summary':{'sample_count':observation['sample_count'],
                                   'speed_min_mps':min(values['ego_speed']),
                                   'speed_max_mps':max(values['ego_speed']),
                                   'driver_attention_to_operation':None},
            'limitations':['Original motion does not establish human attention or a legal outcome']}
    from worker_exchange.native_output import validate_result, physical_result
    validate_result(result)
    result=physical_result(attempt,result)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    with (attempt/'result.json').open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False)
        stream.write('\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(finalize(args.attempt,args.output),allow_nan=False))

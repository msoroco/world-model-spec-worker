"""Finalize saved Native approach speed, excluding curb and parked phases."""
import argparse
import hashlib
import json
from pathlib import Path

from saved_measure import VIDEOS, measure, rows
from source_review import SOURCES, require

CHANNELS = ('kin.speed','kin.velocity','ru.subject')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_approach_speed(measured, config):
    return {'max_approach_speed_mph':measured['max_approach_speed_mph'],
            'approach_frames_above_80_mph':measured['approach_frames_above_80_mph'],
            'approach_frame_range':measured['approach_frame_range'],
            'parked_frame_range':measured['parked_frame_range'],
            'max_parked_speed_mph':measured['max_parked_speed_mph'],
            'requested_approach_speed_mph':config['requested_approach_speed_mph'],
            'requested_speed_used_for_measurement':False,
            'legal_result':None}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt/'result.json').exists() and
            not (attempt/'channels').exists(), 'Retain original saved finalization')
    for name in ('config.json','construction.json','trace.jsonl',
                 'video_frames.jsonl','native-speed.jsonl',*VIDEOS):
        require((attempt/name).is_file(),'Missing required source: '+name)
    config=json.loads((attempt/'config.json').read_text())
    construction=json.loads((attempt/'construction.json').read_text())
    case_id=config['case_id']
    require(case_id==construction['case_id'],'Saved exact case differs')
    review=json.loads((attempt/'approach-review.json').read_text())
    diagnostic=review.get('review_kind')=='synthetic_diagnostic'
    measured=measure(attempt,case_id,diagnostic=diagnostic)
    source=rows(attempt/'native-speed.jsonl')
    channel_defs=construction['recording_description']['channels']
    require({c['name'] for c in channel_defs}==set(CHANNELS),
            'Exact mandatory channels differ')
    channel_dir=attempt/'channels'
    channel_dir.mkdir()
    evidence=[]
    for channel in channel_defs:
        name=channel['name']
        path=channel_dir/(name+'.jsonl')
        with path.open('x') as stream:
            for row in source:
                sample=row['sample']
                if name=='kin.speed':
                    value={'mph':sample['observed_speed_mph'],
                           'phase':row['phase'],'speed_source':'Native velocity vector'}
                elif name=='kin.velocity':
                    value=sample['velocity_xyz_mps']
                else:
                    value={'actor_id':sample['actor_id'],'blueprint':sample['blueprint'],
                           'road_id':sample['road_id'],'lane_id':sample['lane_id']}
                stream.write(json.dumps({'time_s':row['t_s'],'value':value},
                                        allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],
                         'reference':'channels/'+path.name})
    value=measure_approach_speed(measured,config)
    names=('approach-review.json','visibility-review.json',
           'native-speed.jsonl','video_frames.jsonl','trace.jsonl','road.xodr',
           *('source_context/'+name+'.txt' for name in SOURCES),*VIDEOS)
    report={'format':'c229398-saved-approach-v1','case_id':case_id,
            'measurements':{'approach_speed':{'method':'measure_approach_speed',
                'value':value,'sources':{name:digest(attempt/name) for name in names}}},
            'source_join':measured['source_join'],
            'physical_acceptance_claimed':False,'legal_verdict_claimed':False}
    result={'case_id':case_id,'measured_values':value,
            'target_checks':[{'target':'requested approach speed engineering control',
                'requested':config['requested_approach_speed_mph'],
                'measured':measured['max_approach_speed_mph'],
                'method':'Original Native driving-phase velocity, not controller request',
                'tolerance':1.0,
                'matched':abs(measured['max_approach_speed_mph']-
                              config['requested_approach_speed_mph'])<=1.0,
                'physical_cause_confirmed':False,'cause_evidence':list(names)}],
            'setup_confirmed':False,'behavior_attempted':False,
            'maneuver_completed':False,
            'termination_reason':'full 600-frame saved diagnostic interval',
            'physical_failure_flags':['Original approach and curb completion require independent review'],
            'trace_reference':'trace.jsonl','video_references':list(VIDEOS),
            'video_frame_map_reference':'video_frames.jsonl',
            'recording_description':construction['recording_description'],
            'recording_evidence':evidence,'realized_observables':{},
            'provenance_kind':'synthetic_local_diagnostic' if diagnostic else 'original_native',
            'accepted':False}
    from worker_exchange.native_output import write_result
    write_result(attempt,result)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    finalize(args.attempt,args.output)

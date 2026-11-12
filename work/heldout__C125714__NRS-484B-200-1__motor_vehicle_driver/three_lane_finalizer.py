"""Finalize original three-lane roadway and body sources without legal classification."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from three_lane_measurement import measure_three_lane


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__three_lane'


def measure_three_lane_context(root):
    return measure_three_lane(root)


def analyze(attempt):
    root=Path(attempt)
    config_path=root/'config.json'
    if not config_path.is_file():
        raise ValueError('Missing required source: config.json')
    config=json.loads(config_path.read_text())
    if (config.get('selected_case_id'),config.get('law_id'),config.get('cell_id'),
            config.get('actor'))!=(CASE,'NRS-484B-200-1','C125714','motor_vehicle_driver'):
        raise ValueError('Wrong exact three-lane finalizer identity')
    measured=measure_three_lane_context(root)
    return {'format':'worker-analysis-report','case_id':CASE,
            'measurements':{'three_lane_context':{
                'method':'measure_three_lane_context','value':measured,
                'sources':measured['sources']}},
            'limitations':['Synthetic three-lane topology does not establish applicable lane-use law or physical motion.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def build_result(attempt,report):
    root=Path(attempt)
    config=json.loads((root/'config.json').read_text())
    description=config.get('case',{}).get('recording_description')
    if not isinstance(description,dict):
        raise ValueError('Three-lane recording description missing')
    measured=report['measurements']['three_lane_context']['value']
    observations=measured['observations']
    channels={
        'right_half_offset_m':[(row['frame'],row['time_s'],row['minimum_body_right_offset_m']) for row in observations],
        'three_lane_roadway_width_m':[(row['frame'],row['time_s'],row['roadway_width_m']) for row in observations]}
    evidence=[];realized={}
    for name,rows in channels.items():
        path=root/(name+'.jsonl')
        if path.exists():
            raise ValueError('Retain prior derived three-lane channel')
        path.write_text(''.join(json.dumps({'frame':frame,'time_s':time_s,'value':value})+'\n'
                                for frame,time_s,value in rows))
        evidence.append({'name':name,'unit':'m','reference':path.name,
                         'sha256':sha256(path.read_bytes()).hexdigest()})
        realized[name]={'unit':'m','method':'original three-lane map and body readback',
                        'time_window':'all original frames','statistic':'min',
                        'reference':path.name,'value':min(row[2] for row in rows),
                        'sample_window_s':[rows[0][1],rows[-1][1]]}
    return {'case_id':CASE,'measured_values':{'three_lane_context':measured},
            'target_checks':[{'target':'three-lane original context',
                'requested':'three mapped traffic lanes with selected direction pattern and leftward body path',
                'measured':{'roadway_width_m':measured['minimum_roadway_width_m'],
                            'minimum_body_right_offset_m':measured['minimum_body_right_offset_m']},
                'method':'original three-lane map and body readback',
                'tolerance':None,'matched':False,'physical_cause_confirmed':False,
                'cause_evidence':'Original source joins; applicable lane rule and physical review pending'}],
            'setup_confirmed':False,'behavior_attempted':True,'maneuver_completed':False,
            'termination_reason':'Saved three-lane observation complete; physical and applicable-rule context unverified',
            'physical_failure_flags':{'detection_validated':False},
            'trace_reference':'trace.jsonl',
            'video_references':['overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
            'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
            'recording_evidence':evidence,'realized_observables':realized,
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    if output.exists():
        raise ValueError('Retain prior three-lane analysis')
    report=analyze(args.attempt)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))


if __name__=='__main__':
    main()

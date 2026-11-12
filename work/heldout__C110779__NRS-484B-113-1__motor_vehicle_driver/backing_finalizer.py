"""Saved-only original-source backing finalizer; no legal safety decision."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from backing_safety_measurement import measure

PREFIX='heldout__C110779__NRS-484B-113-1__motor_vehicle_driver__'
SUFFIXES={'backing_clear_vehicle','backing_near_vehicle','backing_vehicle_brakes',
          'backing_vehicle_contact','backing_pedestrian','no_reverse_control'}
CAMERAS=('overview','approach','reference_corner','driver_reference')

def digest(path):return sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]

def analyze(attempt):
    root=Path(attempt)
    if not (root/'backing_motion.jsonl').is_file():
        raise ValueError('Missing required source: backing_motion.jsonl')
    config=json.loads((root/'config.json').read_text())
    case=config.get('selected_case_id','')
    if (config.get('law_id'),config.get('cell_id'),config.get('actor'))!=('NRS-484B-113-1','C110779','motor_vehicle_driver') or not case.startswith(PREFIX) or case[len(PREFIX):] not in SUFFIXES:
        raise ValueError('Wrong exact backing finalizer identity')
    corridor=root/'backing_corridor_original.json'
    if not corridor.is_file() or not corridor.read_bytes():
        raise ValueError('Missing original backing corridor source')
    context=json.loads((root/'backing_context.json').read_text())
    if context.get('corridor_source_sha256')!=digest(corridor):
        raise ValueError('Original backing corridor/context hash differs')
    observed=measure(root/'backing_motion.jsonl',root/'backing_contacts.jsonl',root/'backing_context.json')
    mapping=rows(root/'video_frames.jsonl')
    samples=observed['observations']
    if len(mapping)!=len(samples) or any((frame.get('carla_frame'),frame.get('time_s'))!=(sample['frame'],sample['time_s']) for frame,sample in zip(mapping,samples)):
        raise ValueError('Original backing frame map differs from motion source')
    for camera in CAMERAS:
        if not (root/(camera+'.mkv')).is_file():
            raise ValueError('Missing original backing camera source: '+camera)
    return {'format':'worker-analysis-report','case_id':case,
            'measurements':{'backing_safety_observation':{
                'method':'analyze',
                'value':observed,'sources':dict(observed['sources'],
                    **{'backing_corridor_original.json':digest(corridor),
                       'video_frames.jsonl':digest(root/'video_frames.jsonl')})}},
            'limitations':['Reasonable safety and traffic interference require later physical and legal review.',
                           'Source presence does not establish participant visibility in original pixels.'],
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

def build_result(attempt,report):
    root=Path(attempt);config=json.loads((root/'config.json').read_text());observed=report['measurements']['backing_safety_observation']['value']
    channel=root/'backing_safety_observation.jsonl'
    with channel.open('x') as stream:
        for row in observed['observations']:
            stream.write(json.dumps({'frame':row['frame'],'time_s':row['time_s'],'value':row},allow_nan=False)+'\n')
    description=config['case']['recording_description']
    result={'case_id':report['case_id'],'measured_values':{'backing_safety_observation':observed},
        'target_checks':[{'target':'original backing movement and surrounding traffic response',
            'requested':'retained original 20 Hz motion, contact and traffic context',
            'measured':observed['backing_onset_frame'],'method':'original signed longitudinal speed',
            'tolerance':None,'matched':False,'physical_cause_confirmed':False,
            'cause_evidence':'Saved original sources joined; physical and legal review pending'}],
        'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False,
        'termination_reason':'Saved backing sources measured; physical and legal outcome unverified',
        'physical_failure_flags':{'detection_validated':False},'trace_reference':'trace.jsonl',
        'video_references':[name+'.mkv' for name in CAMERAS],
        'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
        'recording_evidence':[{'name':'backing_safety_observation','unit':'structured record',
            'reference':channel.name,'sha256':digest(channel)}],
        'realized_observables':{},'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
    from worker_exchange.native_output import physical_result
    result=physical_result(root,result)
    original=rows(root/'backing_motion.jsonl')
    first=observed['backing_onset_frame'];last=observed['backing_end_frame']
    by_frame={row['frame']:row for row in original}
    if first is not None:
        start,end=by_frame[first],by_frame[last]
        hx,hy=start['ego_heading_xy']
        reverse_distance=-(end['ego']['x_m']-start['ego']['x_m'])*hx-(end['ego']['y_m']-start['ego']['y_m'])*hy
    else:reverse_distance=0.0
    status='met' if first is not None and reverse_distance>=1.0 else 'not_met'
    result['physical_checks']['maneuver']={'status':status,
        'method':'Original backing onset/end and reverse body-center displacement; 1 m engineering completion criterion',
        'intervals':[] if first is None else [{'first_frame':first,'last_frame':last}],
        'sources':observed['sources'],'reverse_displacement_m':reverse_distance,
        'legal_safety_claimed':False}
    result['maneuver_completed']=status=='met'
    result['realized_observables']['reverse_displacement_m']={
        'unit':'m','method':'original signed body-center displacement during backing',
        'time_window':'original backing onset through end','statistic':'final',
        'reference':channel.name,'value':reverse_distance}
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    report=analyze(args.attempt);Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt,build_result(args.attempt,report))
if __name__=='__main__':main()

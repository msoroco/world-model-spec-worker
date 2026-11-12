"""Independent fixed-road comparison of left baseline and passing excursion."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
from right_half_measurement import measure

PREFIX='heldout__C230259__NRS-484B-200-1__motor_vehicle_driver__'

def _rows(path):return [json.loads(s) for s in path.read_text().splitlines() if s]
def _sha(path):return sha256(path.read_bytes()).hexdigest()
def _source(root,name):
    path=root/name
    if not path.is_file() or not path.read_bytes():raise ValueError('Missing original passing comparison source: '+name)
    return path

def audit(baseline_root,passing_root):
    first,second=Path(baseline_root),Path(passing_root)
    if first.resolve()==second.resolve():raise ValueError('Passing comparison repeats one attempt')
    identities=[(first,'baseline_left'),(second,'passing_left')]
    for root,suffix in identities:
        config=json.loads(_source(root,'config.json').read_text())
        if (config.get('selected_case_id')!=PREFIX+suffix or
                (config.get('rate_hz'),config.get('frames'),config.get('duration_s'))!=(20,80,4)):
            raise ValueError('Passing comparison exact case or duration differs')
        if [camera['name'] for camera in config.get('cameras',[])]!=[
                'overview','approach','reference_corner','driver_reference']:
            raise ValueError('Passing comparison camera contract differs')
    names=('ego_road_frames.jsonl','road_exception_context.json',
           'video_frames.jsonl','trace.jsonl')
    left_sources={name:_source(first,name) for name in names}
    pass_sources={name:_source(second,name) for name in names}
    left,passing=(_rows(left_sources[names[0]]),_rows(pass_sources[names[0]]))
    left_map,pass_map=(_rows(left_sources[names[2]]),_rows(pass_sources[names[2]]))
    left_trace,pass_trace=(_rows(left_sources[names[3]]),_rows(pass_sources[names[3]]))
    if len(left)<3 or not (len(left)==len(passing)==len(left_map)==len(pass_map)==len(left_trace)==len(pass_trace)):
        raise ValueError('Passing comparison original frame counts differ')
    fixed=('frame','time_s','road_id','road_center_xy','road_travel_tangent_xy','road_width_m')
    for a,b,ma,mb,ta,tb in zip(left,passing,left_map,pass_map,left_trace,pass_trace):
        if any(a.get(key)!=b.get(key) for key in fixed):
            raise ValueError('Passing comparison road/timing conditions changed')
        if ma!=mb or (ta['frame'],ta['time_s'])!=(tb['frame'],tb['time_s']):
            raise ValueError('Passing comparison frame map or trace timing changed')
    left_context=json.loads(left_sources[names[1]].read_text())
    pass_context=json.loads(pass_sources[names[1]].read_text())
    setup=pass_context.pop('passing_setup',None)
    if pass_context!=left_context or not isinstance(setup,dict) or setup.get('subject_path')!='right_left_right':
        raise ValueError('Passing comparison changed exception context outside setup')
    left_value=measure(left_sources[names[0]],left_sources[names[1]])
    pass_value=measure(pass_sources[names[0]],pass_sources[names[1]])
    if not all(row['whole_body_left_half'] for row in left_value['observations']):
        raise ValueError('Passing baseline did not stay left')
    observations=pass_value['observations']
    if (not all(row['whole_body_right_half'] for row in observations[:2]) or
            not any(row['whole_body_left_half'] for row in observations[2:-1]) or
            not observations[-1]['whole_body_right_half']):
        raise ValueError('Passing excursion/return missing')
    return {'format':'worker-right-half-passing-comparison','baseline_case_id':PREFIX+'baseline_left',
            'passing_case_id':PREFIX+'passing_left','frames':len(left),
            'fixed_original_keys':list(fixed)+['video_frames.jsonl','trace frame/time','exception context except passing_setup'],
            'baseline_road_sha256':_sha(left_sources[names[0]]),
            'passing_road_sha256':_sha(pass_sources[names[0]]),
            'passed':True,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--passing',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=audit(a.baseline,a.passing);Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'frames':result['frames'],'passed':True}))

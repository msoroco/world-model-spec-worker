"""Independently compare retained exact roundabout speed requests."""
import argparse
import hashlib
import json
from pathlib import Path
MPH=2.2369362921

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def audit(root):
    root=Path(root)
    a=rows(root/'current-v2-below-sources/roundabout-speed-history.jsonl')
    b=rows(root/'current-v2-above-sources/roundabout-speed-history.jsonl')
    if len(a)!=600 or len(b)!=600:raise ValueError('Expected 600 original frame rows each')
    if json.loads((root/'current-v2-below-sources/roundabout-survey.json').read_text())!=json.loads((root/'current-v2-above-sources/roundabout-survey.json').read_text()):
        raise ValueError('Fixed roundabout survey differs')
    differences=[]
    for i,(x,y) in enumerate(zip(a,b)):
        for key in ('video_frame','native_frame','time_s','subject_id','position_xyz_m','road_id','lane_id'):
            if x[key]!=y[key]:raise ValueError('Fixed comparison source differs: '+key)
        if x['video_frame']!=i or abs(x['time_s']-i/20)>1e-6 or x['road_id']!=(1 if i<500 else 2):
            raise ValueError('Original frame/time/road join differs')
        if x['velocity_xyz_mps']!=y['velocity_xyz_mps']:differences.append(i)
    if differences!=list(range(500,600)):
        raise ValueError('Requested speed difference window differs')
    if any(x['velocity_xyz_mps'][0]*MPH>80 for x in a) or any(y['velocity_xyz_mps'][0]*MPH<=80 for y in b[500:]):
        raise ValueError('80 mph source contrast differs')
    return {'format':'worker-current-v2-comparison-audit','passed':True,'selected':False,
      'case_ids':[root.name+'__controlled_1',root.name+'__controlled_2'],
      'source_sha256':{'below':sha(root/'current-v2-below-sources/roundabout-speed-history.jsonl'),
                       'above':sha(root/'current-v2-above-sources/roundabout-speed-history.jsonl')},
      'fixed_conditions_verified':['frame/time','subject','road/lane route','position','roundabout survey'],
      'deliberate_difference':'synthetic velocity 29 versus 38 m/s in exit frames 500..599',
      'different_speed_frame_count':100,'physical_or_legal_acceptance':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 a=p.parse_args();a.output.write_text(json.dumps(audit(a.root),indent=2,sort_keys=True)+'\n')

"""Independently compare retained source requests for the two exact cases."""
import argparse
import hashlib
import json
from pathlib import Path

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return [json.loads(x) for x in path.read_text().splitlines()]
def audit(root):
    root=Path(root)
    a=load(root/'current-v2-primary-sources/turn-history.jsonl')
    b=load(root/'current-v2-contrast-sources/turn-history.jsonl')
    if len(a)!=600 or len(b)!=600: raise ValueError('Expected 600 source frames each')
    for i,(left,right) in enumerate(zip(a,b)):
        if left['frame']!=i or right['frame']!=i or left['time_s']!=right['time_s'] or abs(left['time_s']-i/20)>1e-6:
            raise ValueError('Frame/time join differs')
        for key in ('requested_other_xy_m','requested_other_inside_intersection','requested_arrow',
                    'other_traffic_lawful_status','pedestrian_presence_status'):
            if left[key]!=right[key]: raise ValueError('Fixed comparison source differs: '+key)
        if left['original_native_observed'] or right['original_native_observed']:
            raise ValueError('Synthetic source claims Native observation')
    if a[0]['requested_release_frame']!=320 or b[0]['requested_release_frame']!=200:
        raise ValueError('Controlled release frames differ')
    def entry(rows):
        return next(i for i,r in enumerate(rows) if r['requested_ego_inside_intersection'] and r['requested_phase']=='requested_right_turn')
    ea,eb=entry(a),entry(b)
    if ea!=325 or eb!=205 or a[ea]['requested_other_inside_intersection'] or not b[eb]['requested_other_inside_intersection']:
        raise ValueError('Controlled requested contrast differs')
    return {'format':'worker-current-v2-comparison-audit','passed':True,'selected':False,
            'case_ids':[root.name+'__controlled_1',root.name+'__controlled_2'],
            'source_sha256':{'controlled_1':sha(root/'current-v2-primary-sources/turn-history.jsonl'),
                             'controlled_2':sha(root/'current-v2-contrast-sources/turn-history.jsonl')},
            'fixed_conditions_verified':['frame/time','other route','other occupancy','arrow request',
                                          'lawfulness unresolved','pedestrian status unresolved'],
            'deliberate_difference':'ego requested release frame 320 versus 200',
            'first_requested_entry_frames':[ea,eb],
            'physical_or_legal_acceptance':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();args.output.write_text(json.dumps(audit(args.root),indent=2,sort_keys=True)+'\n')

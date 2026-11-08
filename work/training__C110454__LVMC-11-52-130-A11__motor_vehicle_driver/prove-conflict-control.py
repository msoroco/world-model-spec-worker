"""CPU check of the proposed Native crossing-actor brake condition."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from runner_exception import conflict_brake_required

INSIDE=((1.0,-1.0),(2.0,-1.0),(2.0,1.0),(1.0,1.0))
OUTSIDE=((1.0,10.0),(2.0,10.0),(2.0,12.0),(1.0,12.0))
CASES=(('actor_in_junction_ego_approaching',-10.0,INSIDE,True),
       ('actor_cleared_ego_approaching',-10.0,OUTSIDE,False),
       ('actor_in_junction_ego_outside_window',-20.0,INSIDE,False),
       ('actor_absent',-10.0,None,False),
       ('actor_in_junction_ego_past_boundary',8.0,INSIDE,False))

def main():
    rows=[]
    for name,ego_x,actor_body,expected in CASES:
        observed=conflict_brake_required(ego_x,actor_body)
        if observed is not expected:raise ValueError('Conflict control relation differs: '+name)
        rows.append({'case':name,'ego_x_m':ego_x,'actor_body_xy_m':actor_body,
                     'brake_required':observed})
    source=HERE/'native/runner_exception.py'
    proof={'format':'c110454-conflict-control-cpu-proof-v1','passed':True,
           'runner_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
           'rows':rows,'physical_execution_claimed':False,
           'legal_necessity_verdict':None}
    (HERE/'conflict-control-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps(proof,sort_keys=True))

if __name__=='__main__':main()

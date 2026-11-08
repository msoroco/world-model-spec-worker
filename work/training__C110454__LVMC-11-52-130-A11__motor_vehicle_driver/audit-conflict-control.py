"""Independent geometry audit of the proposed conflict brake relation."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def main():
    proof=json.loads((HERE/'conflict-control-proof.json').read_text())
    assert proof['passed'] is True and proof['physical_execution_claimed'] is False
    assert proof['legal_necessity_verdict'] is None and len(proof['rows'])==5
    assert proof['runner_sha256']==hashlib.sha256((HERE/'native/runner_exception.py').read_bytes()).hexdigest()
    observed={}
    for row in proof['rows']:
        body=row['actor_body_xy_m']
        actual=(-18.0<=row['ego_x_m']<=7.0 and body is not None and
                any(-7.0<=vertex[0]<=7.0 and -7.0<=vertex[1]<=7.0 for vertex in body))
        assert actual is row['brake_required'],row['case']
        observed[row['case']]=actual
    assert observed=={'actor_in_junction_ego_approaching':True,
                      'actor_cleared_ego_approaching':False,
                      'actor_in_junction_ego_outside_window':False,
                      'actor_absent':False,
                      'actor_in_junction_ego_past_boundary':False}
    result={'format':'c110454-independent-conflict-control-audit-v1','passed':True,
            'proof_sha256':hashlib.sha256((HERE/'conflict-control-proof.json').read_bytes()).hexdigest(),
            'geometry_cases':len(observed),'physical_execution_claimed':False,
            'statutory_necessity_claimed':False}
    (HERE/'conflict-control-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__':main()

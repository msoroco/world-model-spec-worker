"""Independent source-bound orthogonal versus shallow planned left audit."""
import argparse
import hashlib
import json
from pathlib import Path
from opposing_left_measurement import measure_opposing_left

FIXED = ('opposing_left_participants.jsonl', 'trace.jsonl', 'video_frames.jsonl',
         'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def audit(orthogonal, shallow):
    a,b=Path(orthogonal),Path(shallow)
    ca=json.loads((a/'opposing_left_context.json').read_text());cb=json.loads((b/'opposing_left_context.json').read_text())
    if any(ca[k]!=cb[k] for k in ('junction_id','map_name','turning_actor_id','opposite_actor_id','legal_exception_claimed','opposite_route')) or ca['turning_route'][:-1]!=cb['turning_route'][:-1]:
        raise ValueError('Fixed opposing-left route or actor context changed')
    for name in FIXED:
        if digest(a/name)!=digest(b/name):raise ValueError('Fixed original source changed: '+name)
    ma=measure_opposing_left(a)['value'];mb=measure_opposing_left(b)['value']
    if not (ma['planned_left_cross']>.85 and .5<=mb['planned_left_cross']<=.85 and ma['approach_heading_dot']==mb['approach_heading_dot']<=-.8 and ma['observed_turn_heading_change_rad']==mb['observed_turn_heading_change_rad']):
        raise ValueError('Orthogonal versus shallow planned left contrast missing')
    return {'format':'worker-shallow-left-comparison-proof','comparison_id':'opposing_left_shallow_vs_orthogonal','orthogonal_cross':ma['planned_left_cross'],'shallow_cross':mb['planned_left_cross'],'fixed_source_sha256':{name:digest(a/name) for name in FIXED},'physical_completion_claimed':False,'legal_acceptance_claimed':False}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--orthogonal',required=True);p.add_argument('--shallow',required=True);p.add_argument('--output',required=True);q=p.parse_args();r=audit(q.orthogonal,q.shallow);Path(q.output).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))

"""Synthetic allocation candidate sources for saved-path CPU proof only."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build(center,posted):
    changed=deepcopy(center)
    files=changed['files']
    lanes=[json.loads(line) for line in files['three_lane_frames.jsonl'].splitlines() if line.strip()]
    readback=json.loads(files['three_lane_map_readback.json'])
    ident='center_allocated_posted' if posted else 'center_allocated_unposted'
    sign_id='synthetic-sign-actor' if posted else None
    plan={'allocation_claim':'scenario-authored exclusive same-direction center-lane allocation candidate',
          'allocation_authority_source':None,'same_direction_map_readback':True,
          'center_lane_id':readback['lane_ids']['center'],'road_id':readback['road_id'],
          'posted_sign_candidate':posted,'sign_blueprint':'static.prop.sign.synthetic' if posted else None,
          'sign_actor_id':sign_id,'sign_text_verified':None,'legal_allocation_verified':None}
    files['allocation_plan.json']=json.dumps(plan,allow_nan=False)+'\n'
    rows=[]
    for lane in lanes:
        rows.append({'frame':lane['frame'],'time_s':lane['time_s'],'ego_actor_id':lane['ego_actor_id'],
            'same_direction_map_readback':True,'posted_sign_candidate':posted,
            'sign_actor_id':sign_id,
            'sign_body_vertices_xyz':[[16,2,0],[16,3,0],[16,3,2],[16,2,2]] if posted else []})
    files['allocation_frames.jsonl']=''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=HERE.name+'__'+ident
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['allocation-diagnostic-provenance.json']=json.dumps({'format':'worker-diagnostic-source-note',
        'source':'center-default-diagnostic.json','use':'synthetic mapped same-direction candidate and sign body; no authentic sign text or legal allocation proof',
        'builder':'build_center_allocation_diagnostics.py'})+'\n'
    return changed


def main():
    source=json.loads((HERE/'center-default-diagnostic.json').read_text())
    for posted in (True,False):
        ident='center-allocated-posted' if posted else 'center-allocated-unposted'
        target=HERE/(ident+'-diagnostic.json')
        target.write_text(json.dumps(build(source,posted),separators=(',',':'),allow_nan=False)+'\n')
        rel='work/'+HERE.name+'/'+target.name
        checksum=sha256(target.read_bytes()).hexdigest()
        recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':rel,'sha256':checksum}],
            'generator':{'source':rel,'sha256':checksum}}
        (HERE/(ident+'-diagnostic-recipe.json')).write_text(json.dumps(recipe,indent=2)+'\n')
        print(target,target.stat().st_size)


if __name__=='__main__':main()

"""Add one synthetic mapped center-lane blocker to passing-clear source."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build(clear):
    changed=deepcopy(clear)
    files=changed['files']
    rows=[]
    for line in files['passing_frames.jsonl'].splitlines():
        row=json.loads(line)
        row['other_vehicle_bodies'].append({
            'actor_id':'synthetic-207',
            'center_xy':[row['ego_center_xy'][0]+62,row['center_lane_center_xy'][1]],
            'half_length_m':2,'half_width_m':1})
        rows.append(row)
    files['passing_frames.jsonl']=''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=HERE.name+'__center_passing_near_traffic'
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['passing-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note',
        'source':'center-passing-clear-diagnostic.json',
        'use':'synthetic center blocker in original passing body source; tests fixed-source comparison only; no physical traffic or legal claim',
        'builder':'build_center_passing_near_diagnostic.py'})+'\n'
    return changed


def main():
    source=json.loads((HERE/'center-passing-clear-diagnostic.json').read_text())
    target=HERE/'center-passing-near-traffic-diagnostic.json'
    target.write_text(json.dumps(build(source),separators=(',',':'),allow_nan=False)+'\n')
    rel='work/'+HERE.name+'/'+target.name
    checksum=sha256(target.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input.json','source':rel,'sha256':checksum}],
        'generator':{'source':rel,'sha256':checksum}}
    (HERE/'center-passing-near-traffic-diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(target,target.stat().st_size)


if __name__=='__main__':
    main()

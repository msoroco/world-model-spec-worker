"""Add synthetic upright static obstruction geometry to passing-clear source."""

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
        source=json.loads(line)
        x=source['ego_center_xy'][0]+87.5
        y=source['center_lane_center_xy'][1]
        vertices=[[x+dx,y+dy,z] for z in (0,3.0)
                  for dx,dy in ((-.5,-2),(.5,-2),(.5,2),(-.5,2))]
        rows.append({'frame':source['frame'],'time_s':source['time_s'],
                     'ego_actor_id':source['ego_actor_id'],
                     'occluder_actor_id':'synthetic-208',
                     'ego_center_xy':source['ego_center_xy'],
                     'occluder_vertices_xyz':vertices,
                     'occluder_blueprint':'static.prop.synthetic_wall'})
    files['occluder_frames.jsonl']=''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=HERE.name+'__center_passing_occluded'
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['passing-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note',
        'source':'center-passing-clear-diagnostic.json',
        'use':'synthetic upright wall geometry in original occluder source; no visible occlusion or physical pass claimed',
        'builder':'build_center_passing_occluded_diagnostic.py'})+'\n'
    return changed


def main():
    source=json.loads((HERE/'center-passing-clear-diagnostic.json').read_text())
    target=HERE/'center-passing-occluded-diagnostic.json'
    target.write_text(json.dumps(build(source),separators=(',',':'),allow_nan=False)+'\n')
    rel='work/'+HERE.name+'/'+target.name
    checksum=sha256(target.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':rel,'sha256':checksum}],
            'generator':{'source':rel,'sha256':checksum}}
    (HERE/'center-passing-occluded-diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(target,target.stat().st_size)


if __name__=='__main__':
    main()

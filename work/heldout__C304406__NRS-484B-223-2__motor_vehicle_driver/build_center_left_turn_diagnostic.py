"""Add synthetic connected left-exit map and indicator readback sources."""

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

HERE=Path(__file__).resolve().parent


def build(center):
    changed=deepcopy(center)
    files=changed['files']
    lanes=[json.loads(line) for line in files['three_lane_frames.jsonl'].splitlines()]
    first=lanes[0]
    x=sum(point[0] for point in first['ego_corners_xy'])/4
    y=sum(point[1] for point in first['ego_corners_xy'])/4
    readback=json.loads(files['three_lane_map_readback.json'])
    plan={'approach_road_id':first['road_id'],
          'approach_center_lane_id':readback['lane_ids']['center'],
          'left_exit_road_id':first['road_id']+1,'left_exit_lane_id':1,
          'turn_angle_deg':90,'junction_entered':True,
          'approach_end_xy':[x+20,y],'left_exit_xy':[x+20,y+10],
          'physical_turn_completed':None}
    files['left_turn_plan.json']=json.dumps(plan,allow_nan=False)+'\n'
    rows=[]
    for lane in lanes:
        ego_x=sum(point[0] for point in lane['ego_corners_xy'])/4
        ego_y=sum(point[1] for point in lane['ego_corners_xy'])/4
        rows.append({'frame':lane['frame'],'time_s':lane['time_s'],
                     'ego_actor_id':lane['ego_actor_id'],
                     'ego_center_xy':[ego_x,ego_y],
                     'distance_to_approach_end_m':max(0,plan['approach_end_xy'][0]-ego_x),
                     'left_indicator_requested':True,'left_indicator_readback':True})
    files['left_turn_frames.jsonl']=''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=HERE.name+'__center_left_turn'
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['left-turn-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note','source':'center-default-diagnostic.json',
        'use':'synthetic left-exit map and indicator readback source; no actual turn or legal preparation claim',
        'builder':'build_center_left_turn_diagnostic.py'})+'\n'
    return changed


def main():
    source=json.loads((HERE/'center-default-diagnostic.json').read_text())
    target=HERE/'center-left-turn-diagnostic.json'
    target.write_text(json.dumps(build(source),separators=(',',':'),allow_nan=False)+'\n')
    rel='work/'+HERE.name+'/'+target.name
    checksum=sha256(target.read_bytes()).hexdigest()
    recipe={'format':'worker-fixture-recipe',
        'sources':[{'path':'diagnostic-input.json','source':rel,'sha256':checksum}],
        'generator':{'source':rel,'sha256':checksum}}
    (HERE/'center-left-turn-diagnostic-recipe.json').write_text(json.dumps(recipe,indent=2)+'\n')
    print(target,target.stat().st_size)


if __name__=='__main__':
    main()

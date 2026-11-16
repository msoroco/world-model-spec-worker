"""Materialize the common CPU-reviewed root construction from selected condition_a."""
import copy,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
c=json.loads((HERE/'draft-candidates/condition_a/primary/construction.json').read_text())
config=next(f for f in c['files'] if f['path']=='config.json')
v=json.loads(config['content'])
v['supported_case_ids']=[HERE.name+'__selected_55c68e79__condition_'+s for s in ('a','b')]
for name,plan in zip(('overview','approach','reference_corner','driver_reference'),[(-14,-18,35,-65),(-2,-10,12,-40),(-17,-12,12,-55),(-22,-8,10,-40)]):
 camera=next(x for x in v['cameras'] if x['name']==name)
 camera['pose_strategy']='fixed surveyed crosswalk corridor world camera'
 camera['fov_deg']=90
 camera['xyz_m']=list(plan[:3]);camera['pitch_deg']=plan[3]
config['content']=json.dumps(v,indent=2)+'\n'
c['files']=copy.deepcopy(c['files'])
for f in c['files']:
 path=HERE/f['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text(f['content'])
(HERE/'construction.json').write_text(json.dumps(c,indent=2)+'\n')
print('materialized root construction:',len(c['files']),'files')

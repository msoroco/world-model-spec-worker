"""Materialize portable top-level CPU construction from selected reference primary."""
import json
from pathlib import Path
F=Path(__file__).resolve().parent.parent

draft=json.loads((F/'native/selected-drafts/probe_a/primary/construction.json').read_text())
manifest=json.loads((F/'execution-manifest.json').read_text())
case_ids=[c['case_id'] for c in manifest['cases']]
files=[]
for item in draft['files']:
 target=F/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
 content=item['content']
 if item['path']=='config.json':
  config=json.loads(content)
  config['supported_case_ids']=case_ids
  for camera in config['cameras']:
   camera['pose_strategy']='school bus cabin, passengers and ice cream truck with continuous route coverage'
   camera['fov_deg']=85
  content=json.dumps(config,indent=2)+'\n'
 target.write_text(content)
 files.append({'path':item['path'],'source':'work/'+F.name+'/'+item['path'],'content':content})
draft['files']=files
draft['supported_case_ids']=case_ids
(F/'construction.json').write_text(json.dumps(draft,indent=2)+'\n')
print(json.dumps({'files':len(files),'supported_cases':len(case_ids)}))

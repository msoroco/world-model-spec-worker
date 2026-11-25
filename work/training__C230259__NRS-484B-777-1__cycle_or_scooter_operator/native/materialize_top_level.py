"""Materialize portable top-level CPU construction from selected reference primary."""
import json
from pathlib import Path
F=Path(__file__).resolve().parent.parent

draft=json.loads((F/'native/selected-drafts/reference/primary/construction.json').read_text())
manifest=json.loads((F/'execution-manifest.json').read_text())
case_ids=[c['case_id'] for c in manifest['cases']]
files=[]
for item in draft['files']:
 target=F/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
 target.write_text(item['content'])
 files.append({'path':item['path'],'source':'work/'+F.name+'/'+item['path'],'content':item['content']})
draft['files']=files
draft['supported_case_ids']=case_ids
(F/'construction.json').write_text(json.dumps(draft,indent=2)+'\n')
print(json.dumps({'files':len(files),'supported_cases':len(case_ids)}))

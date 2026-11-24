import copy,hashlib,json
from pathlib import Path
root=Path.cwd();aid='training__C111603__NRS-484B-307-9a__motor_vehicle_driver';p=root/'work'/aid
manifest=json.loads((p/'selected-v2-manifest.json').read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
for entry in manifest['cases']:
 suffix=entry['case_id'].rsplit('__',1)[-1]
 base=json.loads((p/'v2-primary'/suffix/'construction.json').read_text())
 base['files']=[item for item in base['files'] if not any('/native/drafts/'+suffix+'/'+cid+'/' in item['path'] for cid in ('fallback2','fallback3'))]
 for cid in ('fallback2','fallback3'):
  draft=p/'native/drafts'/suffix/cid
  for name in ('assignment-source.json','arrow-intersection.xodr','requested-tracks.jsonl','config.json'):
   base['files'].append({'path':str((draft/name).relative_to(root)),'content':(draft/name).read_text()})
 primary=p/'v2-primary'/suffix/'construction.json'
 primary.write_text(json.dumps(base,indent=2)+'\n')
 entry['construction_sha256']=sha(primary)
 entry['candidates']=[]
 for cid in ('fallback2','fallback3'):
  altered=copy.deepcopy(base)
  altered['status']='selected_cpu_'+cid+'_diagnostic'
  out=p/'selected-v2-candidates'/suffix/cid/'construction.json'
  out.parent.mkdir(parents=True,exist_ok=True)
  out.write_text(json.dumps(altered,indent=2)+'\n')
  trigger=({'source':'original Native ego trajectory joined to source camera frames',
     'metric':'approach arrow/vehicle pixel visibility in standard overview',
     'failure_condition':'signal head or other vehicle occluded in review'} if cid=='fallback2' else
     {'source':'original Native ego and signal timestamps joined to source camera frames',
     'metric':'yield-hold-to-entry duration',
     'failure_condition':'< 3 seconds of observable hold'} )
  entry['candidates'].append({'id':cid,'trigger':trigger,
    'changed_knobs':['camera_policy'] if cid=='fallback2' else ['pre_approach_dwell_s','yield_hold_s'],
    'construction':str(out.relative_to(p)),'construction_sha256':sha(out)})
manifest['status']='selected_cpu_candidate_proof_pending'
(p/'selected-v2-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(sha(p/'selected-v2-manifest.json'))

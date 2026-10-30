"""Declare exact-case original source joins from each saved fixture schema."""
import json,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def selectors(value,prefix=''):
 if isinstance(value,list):
  if value and all(isinstance(r,dict) and type(r.get('frame')) is int for r in value):
   yield prefix,'frame',('time_s' if all('time_s' in r for r in value) else None);return
  if value and all(type(r) is int for r in value) and prefix.endswith('original_frames'):
   yield prefix,None,None;return
  for i,v in enumerate(value):
   if isinstance(v,(dict,list)):yield from selectors(v,prefix+'.'+str(i) if prefix else str(i))
 elif isinstance(value,dict):
  if type(value.get('frame')) is int:
   yield prefix,'frame',('time_s' if 'time_s' in value else None);return
  for key,v in value.items():
   target=prefix+'.'+key if prefix else key
   if isinstance(v,(dict,list)):yield from selectors(v,target)
   elif type(v) is int and key.endswith('_frame') and v>=0:yield target,None,None

def main():
 specs=[]
 for manifest in sorted((ROOT/'work').glob('*/execution-manifest.json')):
  folder=manifest.parent;plan=read(folder/'case-plan.json')
  for entry in read(manifest)['cases']:
   recipe=read(ROOT/entry['fixture_recipe']);sources=[]
   for item in recipe['additions']:
    path=ROOT/item['source']
    if path.suffix not in ('.json','.jsonl'):continue
    value=[json.loads(s) for s in path.read_text().splitlines() if s] if path.suffix=='.jsonl' else read(path)
    for selector,framekey,timekey in selectors(value):
     row={'path':item['path'],'rows_selector':selector,'frame_key':framekey,'full_recording':item['path'] in ('body_history.jsonl','interaction_history.jsonl','speed_samples.jsonl','following_samples.jsonl','reverse_history.jsonl','signal_history.jsonl','truck_history.jsonl','turn_history.jsonl')}
     if timekey:row['time_key']=timekey
     if item['path']=='visibility_samples.jsonl' and not selector:
      row['full_frame_coverage']=True;row['frame_group_key']='approach';row['required_groups']=sorted({r['approach'] for r in value})
     sources.append(row)
   if not sources:raise ValueError('No case-specific original frames in '+entry['case_id'])
   sources.insert(0,{'path':'trace.jsonl','frame_key':'frame','time_key':'time_s','full_recording':True})
   specs.append({'case_id':entry['case_id'],'assignment_id':folder.name,'frame_sources':sources,'pixel_review_obligations':plan['physical_pixel_audits'],'source_declaration':'Exact source selectors from case-specific measurement fixture schema, bound to actual original frame map during Native saved auditing. No diagnostic physical acceptance.'})
 write(ROOT/'work/_shared/source-audit-specs.json',specs)
 print('Declared case-specific source joins:',len(specs))
if __name__=='__main__':main()

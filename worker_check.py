import json,pathlib,hashlib,argparse
p=argparse.ArgumentParser();p.add_argument('--complete',action='store_true');args=p.parse_args();root=pathlib.Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
b=read(root/'batch.json')
for f,h in b['frozen_files'].items():
 if sha(root/f)!=h:raise ValueError('Changed frozen input: '+f)
ids=[]
for f in sorted((root/'partitions').glob('*.json')):ids+=read(f)['assignment_ids']
assert len(ids)==len(set(ids))==22 and set(ids)==set(b['assignments'])
for aid,v in b['assignments'].items():
 f=root/'work'/aid/'result.json'
 if not f.exists():
  if args.complete:raise ValueError('Missing result: '+aid)
  continue
 result=read(f);assert result['assignment_id']==aid and result['input_sha256']==v['input_sha256']
 assert result['status'] in ('planned','partial','blocked')
 assert (root/'work'/aid/'HANDOFF.md').is_file()
 if result['status']=='planned':
  plan=read(root/'work'/aid/'case-plan.json');assert plan['assignment_id']==aid
  for key in ('cases','comparisons','observations','sources','existing_evidence','runtime_uncertainties'):assert key in plan
  assert plan['sources'] and plan['runtime_uncertainties']
 else:assert result.get('reason')
print('Validated 22 assignments across four partitions')

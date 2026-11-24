"""Preserve small full-decode receipts from the current diagnostic proofs."""
import hashlib,json
from pathlib import Path
OWN=Path(__file__).resolve().parent
REPO=OWN.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__=='__main__':
 manifest=json.loads((OWN/'execution-manifest.json').read_text())
 for entry in manifest['cases']:
  short=entry['case_id'].removeprefix(manifest['assignment_id']+'__')
  root=REPO/'.runtime-work'/('c10307-compat-native-v3-'+short)
  mapping=sha(root/'video_frames.jsonl')
  videos={}
  for index,name in enumerate(('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')):
   receipt=json.loads((root/('source-'+str(index)+'.json')).read_text())
   if receipt['mapping_sha256']!=mapping or receipt['video_sha256']!=sha(root/name):
    raise ValueError('source decode receipt changed')
   videos[name]=receipt
  output={'format':'c10307-synthetic-source-media-audit-v1','case_id':entry['case_id'],
          'scope':'CPU diagnostic pixels only; no physical bicycle/rack visibility claim',
          'mapping_sha256':mapping,'videos':videos}
  path=OWN/('cpu-source-media-'+short+'.json')
  path.write_text(json.dumps(output,indent=2)+'\n')
  print(short,sha(path))

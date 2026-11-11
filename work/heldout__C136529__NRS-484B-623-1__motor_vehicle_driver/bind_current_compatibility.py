"""Bind compatibility receipts from finalized fixed-grid proposals."""
from hashlib import sha256
import json
from pathlib import Path
from shutil import copyfile
root=Path(__file__).resolve().parent;repo=root.parents[1]
sha=lambda p:sha256(Path(p).read_bytes()).hexdigest()
path=root/'execution-manifest.json';manifest=json.loads(path.read_text())
for entry in manifest['cases']:
    case=entry['case_id'];slug=case.removeprefix(root.name+'__').replace('__','-')
    for candidate,item in [('primary',entry)]+[(c['id'],c) for c in entry['candidates']]:
        stem=f'{slug}-{candidate}'
        source=repo/'.runtime-work'/f'c136529-{stem}-compat-v8'
        for suffix,filename in [('compatibility.json','compatibility.json'),
                                ('compat.log','compatibility-analysis.log'),
                                ('negative.log','negative-analysis.log')]:
            copyfile(source/filename,root/f'{stem}-{suffix}')
        item['compatibility']={'receipt':f'{stem}-compatibility.json',
                               'sha256':sha(root/f'{stem}-compatibility.json'),
                               'log':f'{stem}-compat.log','negative_log':f'{stem}-negative.log'}
    entry['post_capture']['test_log_sha256']=sha(root/'saved-processing.log')
path.write_text(json.dumps(manifest,indent=2)+'\n')
print('bound',len(manifest['cases'])*4,'current compatibility receipts and saved-only log')

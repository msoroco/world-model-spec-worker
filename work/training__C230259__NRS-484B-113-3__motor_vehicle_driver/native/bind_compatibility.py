"""Bind exact public compatibility receipts to the selected manifest."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def bind():
    path=ROOT/'execution-manifest.json'
    manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[1]
        for candidate in ('primary','fallback1','fallback2'):
            output=(REPO/'.runtime-work/c230259-compat7/controlled_1-primary' if
                (suffix,candidate)==('controlled_1','primary') else
                REPO/'.runtime-work/c230259-compatall'/f'{suffix}-{candidate}')
            proof=json.loads((output/'compatibility.json').read_text())
            if (proof['passed'] is not True or proof['case_id']!=entry['case_id'] or
                proof['candidate_id']!=candidate):
                raise ValueError('Exact public compatibility proof missing')
            destination=ROOT/'native/proofs'/suffix/candidate
            destination.mkdir(parents=True,exist_ok=True)
            names={'compatibility.json':'proof.json',
                'compatibility-analysis.log':'analysis.log',
                'negative-analysis.log':'negative.log'}
            for source,target in names.items():
                shutil.copy2(output/source,destination/target)
            spec={'receipt':str((destination/'proof.json').relative_to(ROOT)),
                'sha256':sha(destination/'proof.json'),
                'log':str((destination/'analysis.log').relative_to(ROOT)),
                'negative_log':str((destination/'negative.log').relative_to(ROOT))}
            if candidate=='primary':
                entry['compatibility']=spec
                entry['negative']={'log':spec['negative_log'],
                    'log_sha256':sha(destination/'negative.log')}
            else:
                item=next(x for x in entry['candidates'] if x['id']==candidate)
                item['compatibility']=spec
                item.pop('compatibility_pending',None)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'compatibility_cases':len(manifest['cases'])*3}))

if __name__=='__main__':bind()

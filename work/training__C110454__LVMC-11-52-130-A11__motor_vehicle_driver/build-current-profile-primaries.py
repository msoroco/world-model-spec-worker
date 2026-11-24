"""Rebind 30-second primary source cameras to the pinned current capture profile."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
RENAME={'intersection':'reference_corner','parking':'driver_reference'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,indent=2)+'\n')

def main():
    old=json.loads((HERE/'draft-30s-primary-manifest.json').read_text())
    new={**old,'format':'worker-unselected-current-profile-primary-manifest-v1','cases':[]}
    for entry in old['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        construction=json.loads((HERE/entry['construction']).read_text())
        for f in construction['files']:
            if f['path']=='config.json':
                cfg=json.loads(f['content'])
                for cam in cfg['cameras']:cam['name']=RENAME.get(cam['name'],cam['name'])
                assert [c['name'] for c in cfg['cameras']]==['overview','approach','reference_corner','driver_reference']
                f['content']=json.dumps(cfg,indent=2)+'\n'
            elif f['path']=='cameras.py':
                f['content']=(HERE/'native/cameras.py').read_text().replace('"intersection"','"reference_corner"').replace('"parking"','"driver_reference"')
            elif f['path']=='finalize.py':
                f['content']=(HERE/'native/finalize.py').read_text().replace("'intersection','parking'","'reference_corner','driver_reference'")
            elif f['path'].startswith('tests/'):
                f['content']=f['content'].replace("'intersection','parking'","'reference_corner','driver_reference'").replace('"intersection","parking"','"reference_corner","driver_reference"')
        construction['status']='unselected_current_profile_cpu_draft'
        p=HERE/'draft-current-primaries'/suffix/'construction.json';write(p,construction)
        new['cases'].append({**entry,'construction':str(p.relative_to(HERE)),
                             'construction_sha256':sha(p),'candidates':[]})
    p=HERE/'draft-current-primary-manifest.json';write(p,new)
    print(json.dumps({'manifest_sha256':sha(p),'case_hashes':{x['case_id']:x['construction_sha256'] for x in new['cases']}},sort_keys=True))
if __name__=='__main__':main()

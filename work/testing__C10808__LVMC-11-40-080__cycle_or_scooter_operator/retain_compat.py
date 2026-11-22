"""Retain exact positive/negative pinned compatibility receipts."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].removeprefix(ROOT.name+'__')
        output=REPO/'.runtime-work'/('c10808-compat-'+('dismount' if suffix=='dismount_before_uturn' else 'mounted'))
        receipt=json.loads((output/'compatibility.json').read_text())
        if (receipt.get('passed') is not True or receipt['case_id']!=entry['case_id']
                or receipt['construction_sha256']!=entry['construction_sha256']):
            raise ValueError('Compatibility receipt missing, wrong case or stale construction')
        files={}
        for name,source in (('receipt','compatibility.json'),
                            ('log','compatibility-analysis.log'),
                            ('negative_log','negative-analysis.log')):
            target=ROOT/('compat-'+suffix+'-'+source)
            shutil.copyfile(output/source,target)
            files[name]=target.name
        files['sha256']=sha(ROOT/files['receipt'])
        files['command']='.venv-cpu/bin/python runtime.py compatibility --manifest work/'+ROOT.name+'/execution-manifest.json --case '+entry['case_id']+' --output .runtime-work/c10808-compat-'+('dismount' if suffix=='dismount_before_uturn' else 'mounted')+' --library runtime/library --validator .runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'
        entry['compatibility']=files
        entry['negative']={'log':files['negative_log']}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

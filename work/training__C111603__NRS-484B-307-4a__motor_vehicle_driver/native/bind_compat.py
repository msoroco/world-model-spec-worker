"""Retain exact current-hash public compatibility receipts and logs."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil

ROOT=Path(__file__).resolve().parent.parent
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest=ROOT/'selected-preflight-manifest.json'
    expected=sha(manifest)
    target=ROOT/'compatibility'
    target.mkdir(exist_ok=True)
    rows=[]
    for entry in json.loads(manifest.read_text())['cases']:
        case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
        source=SCRATCH/('compat-stable-'+suffix)
        if json.loads((source/'candidate-selection.json').read_text())['manifest_sha256']!=expected:
            raise ValueError('Public selection manifest changed: '+case)
        receipt=json.loads((source/'compatibility.json').read_text())
        if not receipt['passed'] or receipt['construction_sha256']!=entry['construction_sha256']:
            raise ValueError('Public compatibility did not pass current construction: '+case)
        names={'receipt':(source/'compatibility.json',target/(suffix+'-compatibility.json')),
               'analysis_log':(source/'compatibility-analysis.log',target/(suffix+'-analysis.log')),
               'negative_log':(source/'negative-analysis.log',target/(suffix+'-negative.log'))}
        retained={}
        for key,(original,destination) in names.items():
            if not original.is_file():raise ValueError('Missing public evidence: '+str(original))
            stage=SCRATCH/('c111603-'+suffix+'-'+key+'.stage')
            shutil.copyfile(original,stage)
            os.replace(stage,destination)
            retained[key]=str(destination.relative_to(ROOT))
            retained[key+'_sha256']=sha(destination)
        command=' '.join(shlex.quote(str(value)) for value in [
            '.venv-cpu/bin/python','-B','runtime.py','compatibility',
            '--manifest',str(manifest),'--case',case,'--output',str(source),
            '--library','runtime/library','--validator',
            str(SCRATCH/'lean-decoder/.lake/build/bin/adapterCheck')])
        rows.append({'case_id':case,**retained,'command':command})
    index={'format':'worker-c111603-compatibility-index-v1','passed':rows}
    stage=SCRATCH/'c111603-compat-index.stage'
    stage.write_text(json.dumps(index,indent=2)+'\n')
    os.replace(stage,target/'index.json')
    print(json.dumps({'passed':len(rows),'preflight_sha256':expected}))

if __name__=='__main__':main()

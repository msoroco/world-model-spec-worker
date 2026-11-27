"""CPU exercise of physical completion and ordered lifecycle contract."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
SCRATCH=REPO/'.runtime-work/c229455-physical'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
def clean_copy(source,destination):Path(destination).write_text(Path(source).read_text().rstrip()+'\n',encoding='utf-8')
def main():
    SCRATCH.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        cid=entry['case_id'];suffix=cid.removeprefix(ROOT.name+'__')
        fixtures=[];lifecycle=None
        for kind in ('complete_motion','incomplete_motion','missing_evidence','lifecycle'):
            output=SCRATCH/(suffix+'-'+kind)
            if output.exists():shutil.rmtree(output)
            saved=output.parent/(output.name+'-saved')
            if saved.exists():shutil.rmtree(saved)
            out_result=Path(str(output)+'-result.json')
            if out_result.exists():out_result.unlink()
            cmd=[sys.executable,str(ROOT/'physical_probe.py'),'--case',cid,
                 '--kind',kind,'--output',str(output)]
            env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',
             SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
             PYTHONPATH=str(REPO/'runtime/scenario_pipeline'))
            proc=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True)
            log=ROOT/('physical-'+suffix+'-'+kind+'.log')
            log.write_text((proc.stdout+proc.stderr).rstrip()+'\n',encoding='utf-8')
            if proc.returncode:raise ValueError(str(log)+' failed')
            record={'kind':kind,'command':shlex.join(cmd),'exit_code':0,
                    'log':log.name,'log_sha256':sha(log)}
            if kind=='lifecycle':
                lifecycle={'events':['capture_finished','encoders_closed','restoration_verified',
                  'native_exit','owner_released','saved_processing_started'],
                  **{k:v for k,v in record.items() if k!='kind'}}
            else:
                result=ROOT/('physical-'+suffix+'-'+kind+'.json')
                clean_copy(out_result,result)
                record.update(result=result.name,result_sha256=sha(result))
                fixtures.append(record)
        receipt=ROOT/('physical-'+suffix+'-receipt.json')
        write(receipt,{'construction_sha256':entry['construction_sha256'],
                       'fixtures':fixtures,'lifecycle':lifecycle})
        entry['physical_preparation']={'receipt':receipt.name,'sha256':sha(receipt)}
        (ROOT/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(suffix,'physical/lifecycle',flush=True)
if __name__=='__main__':main()

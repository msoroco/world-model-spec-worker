"""Exercise independent delivery protocol positive and missing-source rejection."""
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
SCRATCH=REPO/'.runtime-work/c412974-nov26/saved'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def run(cmd,log):
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',
      SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),TMPDIR=str(SCRATCH),
      PYTHONPATH=str(REPO/'runtime/scenario_pipeline'))
    p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True)
    log.write_text(((p.stdout+p.stderr).rstrip() or 'delivery probe exited '+str(p.returncode))+'\n',encoding='utf-8')
    return p.returncode

def main():
    path=ROOT/'execution-manifest.json';manifest=json.loads(path.read_text())
    for entry in manifest['cases']:
        cid=entry['case_id'];suffix=cid.removeprefix(ROOT.name+'__')
        attempt=SCRATCH/('attempt-'+suffix)
        saved=SCRATCH/('processed-'+suffix)
        negative=attempt.parent/(attempt.name+'-negative-audit')
        if negative.exists():shutil.rmtree(negative)
        base=[sys.executable,str(ROOT/'delivery_probe.py'),'--case',cid,
              '--attempt',str(attempt),'--saved-root',str(saved)]
        positive=base+['--mode','positive'];negative_cmd=base+['--mode','missing_source']
        pos_log=ROOT/('delivery-'+suffix+'-positive.log')
        neg_log=ROOT/('delivery-'+suffix+'-negative.log')
        pos_code=run(positive,pos_log);neg_code=run(negative_cmd,neg_log)
        if pos_code or neg_code!=2 or 'sealed original missing or changed: safety-zone-site.json' not in neg_log.read_text():
            raise ValueError('delivery protocol proof failed: '+suffix)
        entry['delivery_acceptance']={'case_id':cid,'sets':['full-test'],
          'cpu_proof_kind':'mock_only_contract_wiring',
          'checks':['native_source','all_participants','time_join','full_video_decode',
                    'actual_pixels','physical_completion'],
          'script':'delivery_audit.py','script_sha256':sha(ROOT/'delivery_audit.py'),
          'command':shlex.join(positive),'test_exit_code':0,'test_log':pos_log.name,
          'test_log_sha256':sha(pos_log),'negative_command':shlex.join(negative_cmd),
          'negative_exit_code':2,
          'negative_expected_error':'sealed original missing or changed: safety-zone-site.json',
          'negative_log':neg_log.name,'negative_log_sha256':sha(neg_log)}
        path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
        print(suffix,'delivery +/-',flush=True)
if __name__=='__main__':main()

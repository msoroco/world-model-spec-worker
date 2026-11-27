"""Bind all controlled independent comparison shape proofs to the case plan."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from comparison_audit import PAIRS
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    path=ROOT/'case-plan.json';plan=json.loads(path.read_text())
    for comparison in plan['comparisons']:
        name=comparison['comparison_id']
        if name not in PAIRS:raise ValueError('unimplemented comparison: '+name)
        cmd=[sys.executable,str(ROOT/'comparison_probe.py'),'--comparison',name]
        env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1'
        p=subprocess.run(cmd,cwd=REPO,env=env,capture_output=True,text=True)
        log=ROOT/('comparison-'+name+'.log');log.write_text((p.stdout+p.stderr).rstrip()+'\n')
        if p.returncode or 'changed-source negative pass' not in log.read_text():
            raise ValueError('comparison proof failed: '+name)
        comparison['status']='source_gated_original_audit'
        comparison['audit']={'entrypoint':'comparison_audit.py',
          'command':'.venv-cpu/bin/python work/'+ROOT.name+
             '/comparison_audit.py --comparison '+name+
             ' --report-map $REPORT_MAP --output $OUTPUT',
          'cpu_probe_command':'.venv-cpu/bin/python work/'+ROOT.name+
             '/comparison_probe.py --comparison '+name,
          'cpu_probe_log':log.name,'cpu_probe_log_sha256':sha(log),
          'cpu_probe_exit_code':0,
          'scope':'synthetic report-shape only; accepted original comparison requires two accepted original reports'}
    path.write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
if __name__=='__main__':main()

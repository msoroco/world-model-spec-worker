"""Bind the paired source-audited diagnostic comparison and rejection proof."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    proofs=[]
    for negative in (False,True):
        label='negative' if negative else 'positive'
        output=REPO/'.runtime-work'/('c111301-pair-'+label)
        args=[str(REPO/'.venv-cpu/bin/python'),str(ROOT/'comparison_probe.py'),
              '--output',str(output)]
        if negative:args.append('--negative')
        run=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        log=ROOT/('comparison-pair-'+label+'.log');log.write_text(run.stdout)
        if negative:
            if run.returncode==0 or 'fixed condition differs: ego_route_sha256' not in run.stdout:
                raise ValueError('fixed-route tamper was not rejected')
        elif run.returncode or json.loads(run.stdout).get('passed') is not True or \
             json.loads(run.stdout).get('response_history_audit',{}).get('passed') is not True:
            raise ValueError('source-audited pair did not pass')
        proofs.append({'command':' '.join(args),'exit_code':run.returncode,
                       'log':log.name,'log_sha256':sha(log)})
    receipt={'format':'worker-comparison-cpu-proof','comparison_id':'manual_wheelchair_path_conflict',
      'script':'comparison_audit.py','script_sha256':sha(ROOT/'comparison_audit.py'),
      'source_auditor':'delivery_audit.py','source_auditor_sha256':sha(ROOT/'delivery_audit.py'),
      'response_auditor':'response_history_audit.py',
      'response_auditor_sha256':sha(ROOT/'response_history_audit.py'),
      'fixture_provenance':'synthetic CPU software diagnostic; no physical acceptance',
      'positive':proofs[0],'negative':proofs[1]}
    path=ROOT/'comparison-proof.json';path.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()

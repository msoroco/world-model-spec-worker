"""CPU selftests for independent original delivery and pair comparison gates."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent
SCRATCH=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    stage=SCRATCH/('c111603-'+path.name+'.stage')
    stage.write_text(content.rstrip()+'\n')
    os.replace(stage,path)


def run(script,id_flag,identifier,expected,suffix):
    base=[sys.executable,'-B',str(ROOT/script),id_flag,identifier,'--self-test']
    positive=subprocess.run(base,capture_output=True,text=True,timeout=30)
    negative=subprocess.run(base+['--negative'],capture_output=True,text=True,timeout=30)
    if (positive.returncode or negative.returncode==0
            or expected not in negative.stderr):
        raise ValueError('Independent audit selftest failed: '+suffix+
                         positive.stderr[-400:]+negative.stderr[-400:])
    directory=ROOT/('delivery-audit' if script=='delivery_audit.py' else 'comparison-audit')
    pos=directory/(suffix+'-positive.log');neg=directory/(suffix+'-negative.log')
    atomic(pos,positive.stdout);atomic(neg,negative.stderr)
    return {'script':script,'script_sha256':sha(ROOT/script),
            'command':' '.join(base),'test_exit_code':0,
            'test_log':str(pos.relative_to(ROOT)),'test_log_sha256':sha(pos),
            'negative_command':' '.join(base+['--negative']),
            'negative_exit_code':negative.returncode,
            'negative_expected_error':expected,
            'negative_log':str(neg.relative_to(ROOT)),
            'negative_log_sha256':sha(neg),
            'original_capture_attested':False}


def main():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    delivery=[]
    for case in plan['cases']:
        ident=case['case_id'];suffix=ident.rsplit('__',1)[-1]
        row=run('delivery_audit.py','--case',ident,
                'Original governed arrow and participant source unverified',suffix)
        row['case_id']=ident;delivery.append(row)
    comparison=[]
    for item in plan['comparisons']:
        ident=item['comparison_id'];suffix=ident.rsplit('__',1)[-1]
        row=run('comparison_audit.py','--comparison',ident,
                'Undeclared comparison source difference',suffix)
        row['comparison_id']=ident;row['case_ids']=item['case_ids'];comparison.append(row)
    atomic(ROOT/'delivery-audit/index.json',json.dumps({
        'format':'worker-c111603-delivery-audit-cpu-proof-v1',
        'cases':delivery,'passed':len(delivery),
        'scope':'auditor predicate selftests; no original capture attested'},indent=2))
    atomic(ROOT/'comparison-audit/index.json',json.dumps({
        'format':'worker-c111603-comparison-audit-tests-v1',
        'comparisons':comparison},indent=2))
    print(json.dumps({'delivery_selftests':len(delivery),
                      'comparison_selftests':len(comparison)}))


if __name__=='__main__':
    main()

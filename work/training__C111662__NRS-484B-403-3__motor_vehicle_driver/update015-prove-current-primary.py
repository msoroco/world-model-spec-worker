"""Run exact primary compatibility and saved processing for each authored U-turn case."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
BASE=REPO/'.runtime-work'/'update015-c111662-current-primary-proof'
MANIFEST=ROOT/'draft-execution-manifest.json'
PYTHON=REPO/'.venv-cpu/bin/python'
RUNTIME=REPO/'runtime.py'
LIBRARY=REPO/'runtime/pipeline/library'
VALIDATOR=REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args,log):
    result=subprocess.run([str(PYTHON),str(RUNTIME),*args],cwd=REPO,capture_output=True,text=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('Proof command failed; inspect '+str(log)+': '+result.stderr[-1200:])
    return result


def run():
    manifest=json.loads(MANIFEST.read_text())
    results=[]
    for entry in manifest['cases']:
        case=entry['case_id'].rsplit('__',1)[-1]
        attempt=BASE/case/'compatibility'
        saved=BASE/case/'saved'
        for path in (attempt,saved):
            if path.exists():shutil.rmtree(path)
            path.parent.mkdir(parents=True,exist_ok=True)
        compatibility_log=ROOT/f'update015-current-{case}-compatibility-command.log'
        command(['compatibility','--manifest',str(MANIFEST),'--case',entry['case_id'],
                 '--output',str(attempt),'--library',str(LIBRARY),
                 '--validator',str(VALIDATOR)],compatibility_log)
        compatibility=json.loads((attempt/'compatibility.json').read_text())
        if compatibility.get('passed') is not True or compatibility.get('candidate_id')!='primary':
            raise ValueError('Primary compatibility receipt incomplete: '+case)
        saved_log=ROOT/f'update015-current-{case}-saved-command.log'
        command(['process-saved','--manifest',str(MANIFEST),'--case',entry['case_id'],
                 '--attempt',str(attempt),'--output',str(saved),'--library',str(LIBRARY),
                 '--validator',str(VALIDATOR)],saved_log)
        processing=saved/'v0001/processing.json'
        receipt=json.loads(processing.read_text())
        if receipt.get('passed') is not True or receipt.get('candidate_id')!='primary':
            raise ValueError('Primary saved-processing receipt incomplete: '+case)
        proof_dir=ROOT/'update015-current-primary'/case
        proof_dir.mkdir(parents=True,exist_ok=True)
        for name,source in [('compatibility.json',attempt/'compatibility.json'),
                            ('analysis.log',attempt/'compatibility-analysis.log'),
                            ('negative-analysis.log',attempt/'negative-analysis.log'),
                            ('processing.json',processing),
                            ('saved-analysis.log',saved/'v0001/analysis.log')]:
            shutil.copyfile(source,proof_dir/name)
        results.append({'case_id':entry['case_id'],'candidate_id':'primary',
                        'construction_sha256':entry['construction_sha256'],
                        'compatibility_passed':True,'saved_processing_passed':True,
                        'compatibility_receipt':str((proof_dir/'compatibility.json').relative_to(ROOT)),
                        'compatibility_sha256':sha(proof_dir/'compatibility.json'),
                        'processing_receipt':str((proof_dir/'processing.json').relative_to(ROOT)),
                        'processing_sha256':sha(proof_dir/'processing.json'),
                        'negative_log_sha256':sha(proof_dir/'negative-analysis.log')})
        print(json.dumps({'case':case,'compatibility':True,'saved_processing':True}),flush=True)
    matrix=ROOT/'update015-current-primary-matrix.json'
    matrix.write_text(json.dumps({'format':'c111662-current-primary-proof-matrix-v1',
                                  'manifest_sha256':sha(MANIFEST),'results':results},indent=2)+'\n')


if __name__=='__main__':run()

"""Prove a fallback against its own source-bound diagnostic and saved-processing path."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PYTHON=REPO/'.venv-cpu/bin/python'
RUNTIME=REPO/'runtime.py'
LIBRARY=REPO/'runtime/pipeline/library'
VALIDATOR=REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prove(case,candidate):
    if case not in ('reference','contrast','divided_reference','divided_opening') or candidate not in ('fallback1','fallback2','fallback3'):
        raise ValueError('Select authored fallback')
    manifest=ROOT/f'draft-execution-manifest-{case}-{candidate}.json'
    case_id=ROOT.name+'__'+case
    base=REPO/'.runtime-work'/'update015-c111662-current-fallback-proof'/case/candidate
    attempt,saved=base/'compatibility',base/'saved'
    for path in (attempt,saved):
        if path.exists():shutil.rmtree(path)
        path.parent.mkdir(parents=True,exist_ok=True)
    proof_dir=ROOT/'update015-current-fallback'/case/candidate
    proof_dir.mkdir(parents=True,exist_ok=True)
    def run(args,name):
        result=subprocess.run([str(PYTHON),str(RUNTIME),*args],cwd=REPO,capture_output=True,text=True)
        (proof_dir/name).write_text(result.stdout+result.stderr)
        if result.returncode:raise ValueError(f'{case}/{candidate} {name}: '+result.stderr[-1300:])
    run(['compatibility','--manifest',str(manifest),'--case',case_id,
         '--candidate',candidate,'--output',str(attempt),
         '--library',str(LIBRARY),'--validator',str(VALIDATOR)],'compat-command.log')
    compatibility=json.loads((attempt/'compatibility.json').read_text())
    if compatibility.get('passed') is not True or compatibility.get('candidate_id')!=candidate:
        raise ValueError('Fallback compatibility receipt incomplete')
    run(['process-saved','--manifest',str(manifest),'--case',case_id,
         '--attempt',str(attempt),'--output',str(saved),
         '--library',str(LIBRARY),'--validator',str(VALIDATOR)],'saved-command.log')
    processing=saved/'v0001/processing.json'
    receipt=json.loads(processing.read_text())
    if receipt.get('passed') is not True or receipt.get('candidate_id')!=candidate:
        raise ValueError('Fallback saved-processing receipt incomplete')
    for name,source in [('compatibility.json',attempt/'compatibility.json'),
                        ('analysis.log',attempt/'compatibility-analysis.log'),
                        ('negative-analysis.log',attempt/'negative-analysis.log'),
                        ('processing.json',processing),('saved-analysis.log',saved/'v0001/analysis.log')]:
        shutil.copyfile(source,proof_dir/name)
    summary={'case_id':case_id,'candidate_id':candidate,'manifest_sha256':sha(manifest),
             'construction_sha256':compatibility['construction_sha256'],
             'compatibility_passed':True,'saved_processing_passed':True,
             'compatibility_sha256':sha(proof_dir/'compatibility.json'),
             'processing_sha256':sha(proof_dir/'processing.json'),
             'negative_log_sha256':sha(proof_dir/'negative-analysis.log')}
    (proof_dir/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'case':case,'candidate':candidate,'compatibility':True,'saved_processing':True}),flush=True)


if __name__=='__main__':prove(sys.argv[1],sys.argv[2])

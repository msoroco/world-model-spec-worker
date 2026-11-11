"""Replay all eight current C132497 compatibility and saved CPU diagnostics."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO/'.runtime-work/c132497-current-all-proof'
PYTHON = REPO/'.venv-cpu/bin/python'
RUNTIME = REPO/'runtime.py'
LIBRARY = REPO/'runtime/pipeline/library'
VALIDATOR = REPO/'.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    result = subprocess.run([str(PYTHON), str(RUNTIME), *map(str,args)], cwd=REPO,
                            capture_output=True, text=True)
    log.write_text(result.stdout+result.stderr)
    if result.returncode:
        raise ValueError('Current CPU command failed: '+str(log)+': '+result.stderr[-1000:])


def main():
    index = json.loads((ROOT/'update015-current-candidate-index.json').read_text())
    results = []
    for item in index['results']:
        case = item['case_id'].rsplit('__',1)[-1]
        candidate = item['candidate_id']
        manifest = ROOT/item['manifest']
        if sha(manifest) != item['manifest_sha256']:
            raise ValueError('Current manifest changed: '+case+'/'+candidate)
        attempt = BASE/case/candidate/'compatibility'
        saved = BASE/case/candidate/'saved'
        for path in (attempt,saved):
            if path.exists(): shutil.rmtree(path)
            path.parent.mkdir(parents=True,exist_ok=True)
        logdir = ROOT/'update015-current-all'/case/candidate
        logdir.mkdir(parents=True,exist_ok=True)
        compat_log = logdir/'current-command.log'
        run(['compatibility','--manifest',manifest,'--case',item['case_id'],
             '--candidate',candidate,'--output',attempt,'--library',LIBRARY,
             '--validator',VALIDATOR],compat_log)
        compatibility = json.loads((attempt/'compatibility.json').read_text())
        if (compatibility.get('passed') is not True or
            compatibility.get('candidate_id') != candidate or
            compatibility.get('construction_sha256') != item['construction_sha256'] or
            'negative_case_source' not in compatibility.get('checks',[])):
            raise ValueError('Current compatibility incomplete: '+case+'/'+candidate)
        saved_log = logdir/'saved-command.log'
        run(['process-saved','--manifest',manifest,'--case',item['case_id'],
             '--attempt',attempt,'--output',saved,'--library',LIBRARY,
             '--validator',VALIDATOR],saved_log)
        processing = json.loads((saved/'v0001/processing.json').read_text())
        if (processing.get('passed') is not True or
            processing.get('candidate_id') != candidate or
            processing.get('missing_evidence') is not False or
            processing.get('originals_preserved') is not True or
            processing.get('timestamp_joins',{}).get('frames') != 240):
            raise ValueError('Current saved processing incomplete: '+case+'/'+candidate)
        for source,target in ((attempt/'compatibility.json','compatibility.json'),
                              (attempt/'negative-analysis.log','negative-analysis.log'),
                              (saved/'v0001/processing.json','processing.json'),
                              (saved/'v0001/analysis.log','saved-analysis.log')):
            shutil.copyfile(source,logdir/target)
        results.append({'case_id':item['case_id'],'candidate_id':candidate,
                        'manifest_sha256':item['manifest_sha256'],
                        'construction_sha256':item['construction_sha256'],
                        'compatibility_sha256':sha(logdir/'compatibility.json'),
                        'negative_log_sha256':sha(logdir/'negative-analysis.log'),
                        'processing_sha256':sha(logdir/'processing.json'),
                        'compatibility_passed':True,'saved_processing_passed':True,
                        'original_native_observed':False})
        print(json.dumps({'case':case,'candidate':candidate,'passed':True}),flush=True)
    matrix = ROOT/'update015-current-all-matrix.json'
    matrix.write_text(json.dumps({'format':'c132497-current-candidate-cpu-matrix-v1',
        'candidate_index_sha256':sha(ROOT/'update015-current-candidate-index.json'),
        'results':results,'physical_acceptance_claimed':False,
        'delivery_ready':False},indent=2)+'\n')
    print(json.dumps({'passed':len(results),'matrix_sha256':sha(matrix)}))


if __name__ == '__main__': main()

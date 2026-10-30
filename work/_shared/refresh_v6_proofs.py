"""Run exact v6 primary and fallback CPU proofs, retaining only small receipts."""
import argparse
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
LIBRARY = ROOT / 'runtime/main-pipeline-v6/library'
VALIDATOR = ROOT / '.runtime-work/v6-selftest-proof/decoder/.lake/build/bin/adapterCheck'
OUTPUT = ROOT / '.runtime-work/v6-case-proofs'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)
def command(*parts): return ' '.join(str(p) for p in parts)

def prove(item):
    folder, case_id, candidate = item
    key = hashlib.sha256((case_id + '|' + candidate).encode()).hexdigest()[:16]
    target = OUTPUT / key
    if target.exists(): shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'execution-manifest.json'
    offline = [str(PYTHON), str(RUNTIME), 'offline', '--manifest', str(manifest), '--case', case_id,
               '--candidate', candidate, '--output', str(target/'offline'), '--python', str(PYTHON)]
    compat = [str(PYTHON), str(RUNTIME), 'compatibility-recipe', '--manifest', str(manifest),
              '--case', case_id, '--candidate', candidate, '--output', str(target/'compat'),
              '--library', str(LIBRARY), '--validator', str(VALIDATOR)]
    env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
    for label, argv in (('offline', offline), ('compat', compat)):
        with (target/(label+'.stdout.log')).open('w') as log:
            result = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=600, check=False)
        if result.returncode:
            return {'case_id': case_id, 'candidate': candidate, 'error': label,
                    'exit_code': result.returncode, 'log': str(target/(label+'.stdout.log'))}
    return {'case_id':case_id, 'candidate':candidate, 'folder':str(folder),
            'target':str(target), 'offline_command':command(*offline), 'compat_command':command(*compat)}

def record(done):
    folder=Path(done['folder']); target=Path(done['target']); case_id=done['case_id']; candidate=done['candidate']
    manifest_path=folder/'execution-manifest.json'; manifest=json.loads(manifest_path.read_text())
    entry=next(e for e in manifest['cases'] if e['case_id']==case_id)
    key=hashlib.sha256((case_id+'|'+candidate).encode()).hexdigest()[:12]
    receipts=folder/'receipts';receipts.mkdir(exist_ok=True)
    paths={}
    for label, source in [('offline',target/'offline/offline.log'),
                          ('compatibility',target/'compat/compatibility.json'),
                          ('analysis',target/'compat/compatibility-analysis.log'),
                          ('negative',target/'compat/negative-analysis.log')]:
        destination=receipts/f'v6-{candidate}-{key}-{label}{source.suffix}'
        shutil.copyfile(source,destination)
        paths[label]=(str(destination.relative_to(folder)),sha(destination))
    construction_sha=entry['construction_sha256'] if candidate=='primary' else entry['candidates'][0]['construction_sha256']
    offline={'command':done['offline_command'],'exit_code':0,'log':paths['offline'][0],
             'log_sha256':paths['offline'][1],'construction_sha256':construction_sha}
    compat={'command':done['compat_command'],'receipt':paths['compatibility'][0],
            'sha256':paths['compatibility'][1],'log':paths['analysis'][0],
            'negative_log':paths['negative'][0], 'exit_code':0}
    if candidate=='primary':
        entry['offline']=offline;entry['compatibility']=compat
        entry['negative']={'log':paths['negative'][0],'log_sha256':paths['negative'][1],'exit_code':1}
    else:
        entry['candidates'][0]['offline']=offline
        entry['candidates'][0]['compatibility']=compat
    write(manifest_path,manifest)
    result_path=folder/'result.json';result=json.loads(result_path.read_text())
    result.setdefault('tests',[]).extend([
        {'command':offline['command'],'exit_code':0,'log':offline['log'],'sha256':offline['log_sha256']},
        {'command':compat['command'],'exit_code':0,'log':compat['receipt'],'sha256':compat['sha256']}])
    write(result_path,result)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--limit',type=int); args=parser.parse_args()
    if not VALIDATOR.is_file(): raise ValueError('Missing v6 Lean decoder')
    items=[]
    for folder in sorted((ROOT/'work').glob('testing__*')):
        path=folder/'execution-manifest.json'
        if path.is_file():
            for entry in json.loads(path.read_text())['cases']:
                for candidate in ('primary','fallback1'):
                    proof = entry if candidate == 'primary' else entry['candidates'][0]
                    receipt = proof.get('compatibility', {}).get('receipt')
                    offline = proof.get('offline', {})
                    if (receipt and offline.get('exit_code') == 0
                            and (folder / receipt).is_file()
                            and (folder / offline.get('log', '')).is_file()):
                        evidence = json.loads((folder / receipt).read_text())
                        if (evidence.get('runtime_manifest_sha256') ==
                                json.loads(path.read_text())['runtime_manifest_sha256']
                                and evidence.get('construction_sha256') == proof.get('construction_sha256')
                                and evidence.get('fixture_recipe_sha256') == sha(
                                    ROOT / entry['fixture_recipe'])):
                            continue
                    items.append((folder,entry['case_id'],candidate))
    if args.limit:items=items[:args.limit]
    failures=[]; completed=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures=[executor.submit(prove,item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            done=future.result()
            if 'error' in done: failures.append(done)
            else: record(done);completed+=1
            if (completed+len(failures))%20==0:
                print(json.dumps({'completed':completed,'failures':len(failures),'total':len(items)}),flush=True)
    write(ROOT/'work/_shared/v6-case-proof-failures.json',failures)
    print(json.dumps({'completed':completed,'failures':failures[:10],'total':len(items)}),flush=True)
    if failures:sys.exit(1)
if __name__=='__main__':main()

"""Refresh four exact primary/fallback CPU proofs after bundle changes."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'execution-manifest.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args,log,output):
    if output.exists():shutil.rmtree(output)
    process=subprocess.run(args,cwd=REPO,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    log.write_text(process.stdout)
    if process.returncode:raise RuntimeError(str(log)+': '+process.stdout[-1200:])


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        label='clear' if entry['case_id'].endswith('clear_path') else 'crossing'
        for ident,target in [('primary',entry),('fallback1',entry['candidates'][0])]:
            suffix='' if ident=='primary' else '-fallback1'
            if suffix:
                off=REPO/'.runtime-work'/('c111301-offline-'+label+suffix)
                log=ROOT/('proof-'+label+suffix+'.log')
                args=[str(REPO/'.venv-cpu/bin/python'),'runtime.py','offline','--manifest',str(MANIFEST),
                    '--case',entry['case_id'],'--output',str(off),'--python',str(REPO/'.venv-cpu/bin/python'),
                    '--candidate',ident]
                run(args,log,off)
                target['offline']={'command':' '.join(args),'exit_code':0,
                    'construction_sha256':target['construction_sha256'],'log':log.name,'log_sha256':sha(log)}
            output=REPO/'.runtime-work'/('c111301-compat-'+label+suffix)
            args=[str(REPO/'.venv-cpu/bin/python'),'runtime.py','compatibility','--manifest',str(MANIFEST),
                  '--case',entry['case_id'],'--output',str(output),'--library',str(REPO/'runtime/library'),
                  '--validator',str(REPO/'.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck')]
            if suffix:args.extend(['--candidate',ident])
            run(args,REPO/'.runtime-work'/('c111301-compat-'+label+suffix+'-command.log'),output)
            receipt=ROOT/('compat-'+label+suffix+'-receipt.json')
            log=ROOT/('compat-'+label+suffix+'-analysis.log')
            negative=ROOT/('compat-'+label+suffix+'-negative.log')
            for source,destination in [('compatibility.json',receipt),('compatibility-analysis.log',log),
                                       ('negative-analysis.log',negative)]:
                shutil.copyfile(output/source,destination)
            target['compatibility']={'receipt':receipt.name,'sha256':sha(receipt),
                'log':log.name,'negative_log':negative.name,'command':' '.join(args)}
        entry['negative']={'log':entry['compatibility']['negative_log']}
        MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()

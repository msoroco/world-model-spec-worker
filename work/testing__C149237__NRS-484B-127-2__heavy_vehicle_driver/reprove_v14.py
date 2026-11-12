"""Reprove all exact truck constructions after Native physical descriptor repair."""
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
MANIFEST=f'work/{HERE.name}/execution-manifest.json'
VALIDATOR='.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def run(name, arguments, output):
    log=HERE/name
    if output.exists():
        if not (output/'offline.log').is_file() and not (output/'compatibility.json').is_file() and not (output/'v0001/processing.json').is_file():
            raise ValueError('Existing incomplete proof output: '+str(output))
        print('retained',name,flush=True)
        return
    with log.open('w') as stream:
        result=subprocess.run(['.venv-cpu/bin/python','runtime.py',*arguments],
                              cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError('Proof failed: '+name+'; see '+str(log))
    print('passed',name,flush=True)


def main():
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        case=entry['case_id']
        suffix=case.split('__')[-1]
        prefix=f'c149237-{suffix}'
        offline=ROOT/'.runtime-work'/f'{prefix}-offline-v14'
        compat=ROOT/'.runtime-work'/f'{prefix}-compat-v14'
        saved=ROOT/'.runtime-work'/f'{prefix}-saved-v14'
        base=['--manifest',MANIFEST,'--case',case]
        common=['--library','runtime/library','--validator',VALIDATOR]
        run(f'{suffix}-offline-launch-v14.log',['offline',*base,'--output',str(offline)],offline)
        run(f'{suffix}-compat-launch-v14.log',['compatibility',*base,'--output',str(compat),*common],compat)
        run(f'{suffix}-saved-launch-v14.log',['process-saved',*base,'--attempt',str(compat),
            '--output',str(saved),*common],saved)
        for candidate in entry['candidates']:
            ident=candidate['id']
            stem=f'{prefix}-{ident}'
            fallback_base=[*base,'--candidate',ident]
            offline=ROOT/'.runtime-work'/f'{stem}-offline-v14'
            compat=ROOT/'.runtime-work'/f'{stem}-compat-v14'
            run(f'{suffix}-{ident}-offline-launch-v14.log',
                ['offline',*fallback_base,'--output',str(offline)],offline)
            run(f'{suffix}-{ident}-compat-launch-v14.log',
                ['compatibility',*fallback_base,'--output',str(compat),*common],compat)


if __name__=='__main__':
    main()

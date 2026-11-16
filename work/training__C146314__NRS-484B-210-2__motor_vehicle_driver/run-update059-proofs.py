"""Reprove all selected CPU candidates after a canonical case edit."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
PYTHON=Path(sys.executable)
RUNTIME=REPO/'runtime.py'
VALIDATOR=REPO/'.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'
LIBRARY=REPO/'runtime/pipeline/library'


def run(label,*arguments):
    log=ROOT/('update059-'+label+'.log')
    with log.open('w') as output:
        subprocess.run([str(PYTHON),*map(str,arguments)],cwd=REPO,
                       stdout=output,stderr=subprocess.STDOUT,check=True)
    print(label,flush=True)

for witness in ('reference','contrast'):
    case=ROOT.name+'__'+witness
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        prefix=REPO/'.runtime-work'/f'c146314-210-2-{witness}-{candidate}'
        offline=Path(str(prefix)+'-offline-update059')
        compat=Path(str(prefix)+'-compat-update059')
        unified=ROOT/'execution-manifest-unified-draft.json'
        diagnostic=ROOT/f'execution-manifest-diagnostic-{witness}-{candidate}.json'
        if witness=='reference' and candidate!='primary':
            diagnostic=ROOT/f'execution-manifest-diagnostic-reference-{candidate}.json'
        manifest=unified if candidate=='primary' else diagnostic
        run(witness+'-'+candidate+'-offline',RUNTIME,'offline','--manifest',unified,
            '--case',case,'--candidate',candidate,'--output',offline)
        run(witness+'-'+candidate+'-compat',RUNTIME,'compatibility','--manifest',manifest,
            '--case',case,'--candidate',candidate,'--output',compat,
            '--library',LIBRARY,'--validator',VALIDATOR)
        run(witness+'-'+candidate+'-saved',ROOT/'run-reference-fallback-saved.py',candidate,witness)

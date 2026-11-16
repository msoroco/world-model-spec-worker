"""Rebuild exact selected bundles after canonical semantic-case alignment."""
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parent
PYTHON=Path(sys.executable)


def run(label,*arguments):
    log=ROOT/('update062-'+label+'.log')
    with log.open('w') as output:
        subprocess.run([str(PYTHON),*map(str,arguments)],cwd=ROOT.parents[1],
                       stdout=output,stderr=subprocess.STDOUT,check=True)
    print(label,flush=True)

for witness in ('reference','contrast'):
    run(witness+'-primary-build',ROOT/'build-selected-primary.py',witness)
    run(witness+'-fallbacks-build',ROOT/'build-reference-fallbacks.py',witness)
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        run(witness+'-'+candidate+'-diagnostic-build',ROOT/'build-selected-diagnostic.py',candidate,witness)
    run(witness+'-manifest-build',ROOT/'build-draft-manifest.py',witness)
    run(witness+'-diagnostic-manifests-build',ROOT/'build-reference-diagnostic-manifests.py',witness)
run('unified-manifest-build',ROOT/'build-unified-draft.py')

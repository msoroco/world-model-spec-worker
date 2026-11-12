"""Recreate persistent diagnostic attempts for independent exact delivery audits."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DRAFT=HERE/'listener-sweep'
paths=(HERE/'case-plan.json',HERE/'proposals/cases.json')
original={path:path.read_bytes() for path in paths}
try:
    paths[0].write_bytes((DRAFT/'case-plan.json').read_bytes())
    paths[1].write_bytes((DRAFT/'proposals/cases.json').read_bytes())
    for offset in (2,4,6):
        prefix=f'listener-{offset}m'
        case=HERE.name+f'__ped_horn_listener_{offset}m'
        command=[sys.executable,'runtime.py','compatibility','--manifest',
                 str((HERE/f'{prefix}-manifest.json').relative_to(ROOT)),
                 '--case',case,'--output',f'.runtime-work/c111603-{prefix}-delivery-attempt',
                 '--library','runtime/library','--validator',
                 '.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
        with (HERE/f'{prefix}-delivery-compatibility.log').open('w') as stream:
            subprocess.run(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,check=True)
        print(case,'persistent_diagnostic_attempt_ready',flush=True)
finally:
    for path,data in original.items(): path.write_bytes(data)

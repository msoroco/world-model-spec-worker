"""Replay draft saved proofs with canonical plan and proposals restored in finally."""
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DRAFT=HERE/'listener-sweep'
paths=(HERE/'case-plan.json', HERE/'proposals/cases.json')
original={path:path.read_bytes() for path in paths}
try:
    paths[0].write_bytes((DRAFT/'case-plan.json').read_bytes())
    paths[1].write_bytes((DRAFT/'proposals/cases.json').read_bytes())
    subprocess.run([sys.executable,str(HERE/'prove_listener_sweep_primary.py')],cwd=ROOT,check=True)
finally:
    for path,data in original.items(): path.write_bytes(data)

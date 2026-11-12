"""Construct and prove three distinct risk-triggered horn fallbacks."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
SOURCE=REPO/'work/heldout__C111603__NRS-484B-413-1__motor_vehicle_driver'
PY=str(REPO/'.venv-cpu/bin/python')
CASE=ROOT.name+'__pedestrian_horn_before_turn'
MANIFEST=ROOT/'execution-manifest.json'
manifest=json.loads(MANIFEST.read_text())
entry=manifest['cases'][0]
def digest(p):return sha256(Path(p).read_bytes()).hexdigest()
def run(cmd,log):
    with log.open('w') as stream:subprocess.run(cmd,cwd=REPO,stdout=stream,stderr=subprocess.STDOUT,check=True)
source_manifest=json.loads((SOURCE/'execution-manifest.json').read_text())
source_case=next(c for c in source_manifest['cases'] if c['case_id'].endswith('__ped_horn_audio'))
for source_candidate in source_case['candidates']:
    name=source_candidate['id']
    target=ROOT/f'pedestrian-horn-{name}-construction.json'
    data=(SOURCE/source_candidate['construction']).read_text().replace('C111603','C111610').replace('__ped_horn_audio','__pedestrian_horn_before_turn')
    target.write_text(data)
    candidate={'id':name,'construction':target.name,'construction_sha256':digest(target),'trigger':source_candidate['trigger'],'changed_knobs':source_candidate['changed_knobs']}
    entry['candidates'].append(candidate)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    base=[PY,'runtime.py','offline','--manifest',str(MANIFEST.relative_to(REPO)),'--case',CASE,'--candidate',name]
    cmd=base+['--output',f'.runtime-work/c111610-horn-{name}-offline-v1','--python',PY]
    log=ROOT/f'pedestrian-horn-{name}-offline.log'
    run(cmd,log)
    candidate['offline']={'command':' '.join(cmd),'exit_code':0,'log':log.name,'log_sha256':digest(log),'construction_sha256':candidate['construction_sha256']}
    output=REPO/f'.runtime-work/c111610-horn-{name}-compat-v1'
    cmd=[PY,'runtime.py','compatibility','--manifest',str(MANIFEST.relative_to(REPO)),'--case',CASE,'--candidate',name,'--output',str(output.relative_to(REPO)),'--library','runtime/library','--validator','.runtime-work/fire-decoder/.lake/build/bin/adapterCheck']
    log=ROOT/f'pedestrian-horn-{name}-compatibility.log'
    run(cmd,log)
    receipt=ROOT/f'pedestrian-horn-{name}-receipt.json'
    analysis=ROOT/f'pedestrian-horn-{name}-analysis.log'
    negative=ROOT/f'pedestrian-horn-{name}-negative.log'
    for a,b in [('compatibility.json',receipt),('compatibility-analysis.log',analysis),('negative-analysis.log',negative)]:shutil.copy2(output/a,b)
    assert json.loads(receipt.read_text())['passed']
    candidate['compatibility']={'receipt':receipt.name,'sha256':digest(receipt),'log':analysis.name,'negative_log':negative.name}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print(name,'offline, compatibility and negative source check passed',flush=True)

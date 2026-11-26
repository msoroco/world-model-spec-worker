"""Record exact current selected-draft and independent CPU mechanics outputs."""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
FOLDER=HERE.parent
ROOT=FOLDER.parents[1]


def save(path,text):
    lines=[line.rstrip() for line in text.splitlines()]
    while lines and not lines[-1]: lines.pop()
    path.write_text('\n'.join(lines)+'\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    env=dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE']='1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(ROOT/'.runtime-work/c385967-pipeline')
    env['TMPDIR']=str(ROOT/'.runtime-work/c385967-tmp')
    for suffix in ('a','b'):
        case=FOLDER.name+'__probe_'+suffix
        for candidate in ('primary','fallback1'):
            source=ROOT/f'.runtime-work/c385967-offline6-{suffix}-{candidate}/offline.log'
            if not source.is_file(): raise ValueError('Missing current selected offline proof')
            save(HERE/f'selected-{suffix}-{candidate}-offline.log',source.read_text())
        for negative in (False,True):
            mode='--negative-selftest' if negative else '--selftest'
            run=subprocess.run([sys.executable,str(HERE/'delivery_audit.py'),
                '--case',case,mode],cwd=ROOT,env=env,capture_output=True,text=True)
            if run.returncode != (1 if negative else 0):
                raise ValueError('Unexpected delivery audit exit: '+case+mode)
            name=f'delivery-{suffix}-'+('negative' if negative else 'positive')+'.log'
            save(HERE/name,run.stdout+run.stderr)
        draft=json.loads((HERE/'selected-draft-manifest.json').read_text())
        construction=next(item for item in draft['cases'] if item['case_id']==case)['construction_sha256']
        fixtures=[]
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            result=HERE/f'physical-{suffix}-{kind}.json'
            if not result.is_file(): raise ValueError('Missing physical outcome result')
            log=HERE/f'physical-{suffix}-{kind}.log'
            save(log,'Synthetic source-shaped physical '+kind+' -> '+
                json.loads(result.read_text())['physical_checks']['maneuver']['status'])
            command=(f'.venv-cpu/bin/python work/{FOLDER.name}/native/prove_physical.py '
                     f'--condition {suffix} --kind {kind} --output work/{FOLDER.name}/native/{result.name}')
            fixtures.append({'kind':kind,'command':command,'exit_code':0,
                'log':'native/'+log.name,'log_sha256':sha(log),
                'result':'native/'+result.name,'result_sha256':sha(result)})
        life=HERE/f'physical-{suffix}-lifecycle.log'
        save(life,'Synthetic fixture lifecycle: capture finished, encoders closed, restoration verified, Native exited, owner released, saved processing started. No original Native owner acquired.')
        receipt=HERE/f'physical-{suffix}-receipt.json'
        receipt.write_text(json.dumps({'format':'c385967-physical-preparation-receipt-v1',
            'case_id':case,'construction_sha256':construction,'fixtures':fixtures,
            'lifecycle':{'events':['capture_finished','encoders_closed',
                'restoration_verified','native_exit','owner_released','saved_processing_started'],
                'exit_code':0,'log':'native/'+life.name,'log_sha256':sha(life),
                'scope':'synthetic CPU lifecycle mock; no original Native session acquired'},
            'scope':'synthetic CPU triad; original Native physical acceptance unverified'},
            indent=2)+'\n')
        print(case,'selected drafts offline and delivery mechanics recorded')


if __name__=='__main__':main()

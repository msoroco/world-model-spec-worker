"""Start exact-case saved processing only after operator-attested release."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

import runner


def require(value,message):
    if not value:raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def command(case,attempt,output,owner_receipt,library,validator,manifest=None):
    manifest=Path(manifest or runner.selected_manifest()).resolve()
    runner.check(manifest)
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    owner_receipt=Path(owner_receipt).resolve()
    require(attempt!=output and attempt not in output.parents,
            'Derived output must be outside original acquisition')
    selection=read(attempt/'candidate-selection.json')
    entries=[e for e in read(manifest)['cases'] if e['case_id']==case]
    require(len(entries)==1 and selection.get('case_id')==case and
            selection.get('manifest_sha256')==runner.sha(manifest),
            'Saved processing selects another exact case or manifest')
    candidate=selection.get('candidate_id')
    entry=entries[0]
    choices=[{'id':'primary','construction_sha256':entry['construction_sha256']},
             *entry.get('candidates',[])]
    selected=[item for item in choices if item['id']==candidate]
    require(len(selected)==1 and
            selection.get('construction_sha256')==selected[0]['construction_sha256'] and
            runner.sha(attempt/'construction.json')==selected[0]['construction_sha256'],
            'Saved processing candidate construction changed')
    native_exit=attempt/'native-exit.json'
    seal=attempt/'capture-seal.json'
    require(native_exit.is_file() and seal.is_file(),
            'Native capture seal or exit receipt missing')
    exit_record=read(native_exit)
    require(exit_record.get('event')=='native_exit' and
            exit_record.get('capture_seal_sha256')==runner.sha(seal),
            'Native exit does not bind sealed capture')
    require(owner_receipt.is_file(),'Operator owner-release receipt missing')
    owner=read(owner_receipt)
    require(owner.get('event')=='owner_released' and
            owner.get('operator_attested') is True and
            owner.get('no_resource_operation_performed') is True and
            owner.get('native_construction_sha256')==
            runner.sha(attempt/'construction.json') and
            owner.get('native_exit_sha256')==runner.sha(native_exit),
            'Operator release is absent or bound to another Native exit')
    return [sys.executable,str(runner.REPO/'runtime.py'),'process-saved',
            '--manifest',str(manifest),'--case',case,
            '--attempt',str(attempt),'--output',str(output),
            '--library',str(Path(library).resolve()),
            '--validator',str(Path(validator).resolve()),
            '--owner-release-receipt',str(owner_receipt)]


def execute(*args,**kwargs):
    planned=command(*args,**kwargs)
    output=Path(planned[planned.index('--output')+1])
    previous=set(output.glob('v[0-9][0-9][0-9][0-9]/processing.json'))
    subprocess.run(planned,cwd=runner.REPO,check=True)
    versions=set(output.glob('v[0-9][0-9][0-9][0-9]/processing.json'))-previous
    require(len(versions)==1,'Pinned saved processing produced no unique new receipt')
    receipt=read(next(iter(versions)))
    attempt=Path(planned[planned.index('--attempt')+1])
    candidate=read(attempt/'candidate-selection.json')['candidate_id']
    require(receipt.get('case_id')==planned[planned.index('--case')+1] and
            receipt.get('candidate_id')==candidate and
            receipt.get('passed') is True and
            receipt.get('recorded_only') is True and
            receipt.get('originals_preserved') is True and
            receipt.get('missing_evidence') is False and
            receipt.get('events',[None])[0]=='saved_processing_started',
            'Saved processing start was not recorded')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--case',required=True);p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True);p.add_argument('--owner-release-receipt',required=True)
    p.add_argument('--library',required=True);p.add_argument('--validator',required=True)
    p.add_argument('--manifest')
    a=p.parse_args()
    print(json.dumps(execute(a.case,a.attempt,a.output,a.owner_release_receipt,
                             a.library,a.validator,a.manifest),sort_keys=True))

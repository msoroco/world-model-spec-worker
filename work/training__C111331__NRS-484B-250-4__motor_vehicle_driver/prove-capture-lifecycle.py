"""Exercise synthetic Native closure, owner release, then saved-only processing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from worker_exchange.runtime_cli import materialize
from worker_exchange.native_output import seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release,run

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MANIFEST=ROOT/'stop-reference-construction-manifest.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(case):
    manifest=json.loads(MANIFEST.read_text())
    entry=next((e for e in manifest['cases'] if e['case_id']==case),None)
    if entry is None:raise ValueError('Select exact case')
    suffix=entry['id'];source=REPO/'.runtime-work'/('c111331-2504-unified-v1-compat-'+suffix+'-primary')
    if not (source/'compatibility.json').is_file():
        source=REPO/'.runtime-work'/('c111331-2504-unified-v2-compat-'+suffix+'-primary')
    if suffix=='prior_stop_yield' and (REPO/'.runtime-work/c111331-2504-cautious-v1-compat-primary/compatibility.json').is_file():
        source=REPO/'.runtime-work/c111331-2504-cautious-v1-compat-primary'
    receipt=json.loads((source/'compatibility.json').read_text())
    if receipt.get('passed') is not True or receipt.get('case_id')!=case:
        raise ValueError('Exact public compatibility source required')
    output=Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    if '.runtime-work' not in output.parts:raise ValueError('Use ignored scratch')
    attempt=output/('lifecycle-'+suffix+'-attempt');saved=output/('lifecycle-'+suffix+'-saved')
    for path in (attempt,saved):
        if path.exists():shutil.rmtree(path)
    materialize(MANIFEST,case,attempt)
    for relative,digest in receipt['fixture_manifest'].items():
        original=source/relative;destination=attempt/relative
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(original,destination)
        if not relative.endswith('.mkv') and sha(destination)!=digest:
            raise ValueError('Fixture source changed during lifecycle staging: '+relative)
    (attempt/'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
        'original_native_observed':False},indent=2)+'\n')
    seal=seal_capture(attempt,frames=600,
        restoration={'restored':True,'synthetic_diagnostic':True},errors=[],
        encoder_exit_codes={name:0 for name in
            ('overview','approach','reference_corner','driver_reference')})
    exit_receipt=record_native_exit(attempt)
    owner_path=attempt/'owner-release.json'
    owner=acknowledge_owner_release(attempt,owner_path,True)
    processed=run(MANIFEST,case,attempt,saved,REPO/'runtime/library',
        REPO/'.runtime-work/c111331-2504-decoder/.lake/build/bin/adapterCheck',owner_path)
    events=seal['events']+[exit_receipt['event'],owner['event'],processed['events'][0]]
    expected=['capture_finished','encoders_closed','restoration_verified',
        'native_exit','owner_released','saved_processing_started']
    if events!=expected or not processed['passed'] or not processed['recorded_only']:
        raise AssertionError('Synthetic lifecycle order differs')
    if not processed['originals_preserved'] or processed['timestamp_joins']['frames']!=600:
        raise AssertionError('Saved source or frame join changed')
    folder=ROOT/'physical-preparation'/suffix;folder.mkdir(parents=True,exist_ok=True)
    log=folder/'lifecycle.log'
    log.write_text('PASS '+case+' synthetic capture closure, owner release and saved-only processing; no physical acceptance\n')
    return {'events':events,'exit_code':0,'log':str(log.relative_to(ROOT)),
        'log_sha256':sha(log),'case_id':case,'synthetic_diagnostic':True,
        'physical_acceptance_claimed':False,
        'saved_processing_receipt_sha256':sha(saved/'v0001/processing.json')}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    a=p.parse_args();print(json.dumps(prove(a.case),indent=2,sort_keys=True))

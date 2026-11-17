"""Prove adjacent no-deposit finalizer and empty source inventories."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
CASE=ROOT.name+'__mail_adjacent_no_deposit'
MANIFEST=ROOT/'execution-manifest-diagnostic-mail-adjacent-no-deposit-draft.json'
spec=importlib.util.spec_from_file_location('emergency_no_business_sources',
    ROOT/'prove-emergency-no-business-source.py')
SOURCE=importlib.util.module_from_spec(spec)
spec.loader.exec_module(SOURCE)
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize


def source_rows(attempt,*,inject_worker=False,inject_parcel=False):
    SOURCE.source_rows(attempt,inject_worker=inject_worker)
    with (attempt/'native-mail-parcel-absence.jsonl').open('w') as stream:
        egos=[json.loads(line) for line in (attempt/'native-raw-actors.jsonl').read_text().splitlines()]
        for ego in egos:
            stream.write(json.dumps({
                'frame':ego['frame'],'native_frame':ego['native_frame'],
                'time_s':ego['time_s'],'source_kind':ego['source_kind'],
                'parcel_actor_ids':[3] if inject_parcel else [],
                'inventory_source':'world.get_actors().filter(static.prop.box*)'},
                allow_nan=False)+'\n')


def run(attempt):
    env=os.environ.copy()
    env['PYTHONPATH']=str(REPO/'runtime/pipeline/scenario_pipeline')
    return subprocess.run([sys.executable,str(attempt/'finalize_selected.py'),
        '--attempt',str(attempt),'--output',str(attempt/'analysis-report.json')],
        cwd=attempt,env=env,text=True,capture_output=True)


def prove(candidate):
    if candidate not in ('primary','fallback1','fallback2','fallback3'):
        raise ValueError('Unknown no-deposit candidate')
    with tempfile.TemporaryDirectory(dir=REPO/'.runtime-work',
                                     prefix='c150142-mail-no-deposit-source-') as temp:
        base=Path(temp)
        positive=base/'positive'
        materialize(MANIFEST,CASE,positive,candidate)
        source_rows(positive)
        passed=run(positive)
        if passed.returncode:
            raise AssertionError('No-deposit finalizer failed: '+passed.stderr[-1600:])
        observed=json.loads((positive/'analysis-report.json').read_text())[
            'measurements']['signed_curb_observation']['value']
        if observed['red_curb_stationary_duration_s']!=12 or \
                not observed['mailbox_present'] or observed['sign_present'] or \
                observed['recorded_activity_events']!=[] or \
                observed['expeditious_mail_deposit_established'] is not None:
            raise AssertionError('No-deposit observation differs')
        missing=base/'missing-parcel-source'
        materialize(MANIFEST,CASE,missing,candidate)
        SOURCE.source_rows(missing)
        rejected=run(missing)
        if rejected.returncode==0 or \
                'Missing required source: native-mail-parcel-absence.jsonl' not in rejected.stderr:
            raise AssertionError('Missing parcel inventory accepted')
        worker=base/'unexpected-worker'
        materialize(MANIFEST,CASE,worker,candidate)
        source_rows(worker,inject_worker=True)
        rejected=run(worker)
        if rejected.returncode==0 or \
                'No-deposit case contains a mail worker' not in rejected.stderr:
            raise AssertionError('Unexpected worker accepted')
        parcel=base/'unexpected-parcel'
        materialize(MANIFEST,CASE,parcel,candidate)
        source_rows(parcel,inject_parcel=True)
        rejected=run(parcel)
        if rejected.returncode==0 or \
                'No-deposit case contains a parcel prop' not in rejected.stderr:
            raise AssertionError('Unexpected parcel accepted')
    return {'case_id':CASE,'candidate_id':candidate,
        'source_kind':'synthetic_native_sample','stationary_duration_s':12,
        'empty_worker_and_parcel_inventories_derived':True,
        'missing_parcel_source_rejected':True,
        'unexpected_worker_rejected':True,'unexpected_parcel_rejected':True,
        'actual_mail_absence_established':False,'original_native_observed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',default='primary')
    args=parser.parse_args()
    print(json.dumps(prove(args.candidate),sort_keys=True))

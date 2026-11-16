"""Independent CPU audit of fresh saved officer-response source attempts."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',str(ROOT/'.runtime-work/c111305-pipeline-output'))
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.native_output import seal_capture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import acknowledge_owner_release,copy_sources,record_native_exit,run as process_saved
spec=importlib.util.spec_from_file_location('independent_officer_audit',HERE/'delivery_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def run(case_id,negative=False):
    manifest=HERE/'provisional-manifest.json'
    entry=next((e for e in json.loads(manifest.read_text())['cases'] if e['case_id']==case_id),None)
    if entry is None:raise ValueError('unknown exact officer case')
    with TemporaryDirectory(prefix='officer-acceptance-',dir=ROOT/'.runtime-work') as tmp:
        base=Path(tmp);make_fixture(ROOT,ROOT/entry['fixture_recipe'],base/'fixture')
        make_attempt(manifest,case_id,base/'attempt');copy_sources(base/'fixture',base/'attempt')
        attempt=base/'attempt';(attempt/'acquisition-provenance.json').write_text(json.dumps({'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,'fixture_scope':'CPU acceptance protocol only'})+'\n')
        frames=sum(bool(line.strip()) for line in (attempt/'video_frames.jsonl').read_text().splitlines())
        seal=seal_capture(attempt,frames=frames,restoration={'restored':True},errors=[],encoder_exit_codes={name:0 for name in ('overview','approach','reference_corner','driver_reference')},context={'fixture_scope':'CPU acceptance protocol only'})
        if seal['events']!=['capture_finished','encoders_closed','restoration_verified']:raise ValueError('capture closure out of order')
        record_native_exit(attempt);owner=base/'owner-release.json';acknowledge_owner_release(attempt,owner,True)
        process_saved(manifest,case_id,attempt,base/'processing',ROOT/'runtime/library',ROOT/'.runtime-work/fire-decoder/.lake/build/bin/adapterCheck',owner_receipt=owner)
        analysis=base/'processing/v0001/analysis'
        result=audit.audit_saved_sources(analysis,missing_source='officer_direction.json' if negative else None)
        complete=json.loads((HERE/'physical'/f'{case_id.split("__")[-1]}-complete_motion.json').read_text())
        if complete['physical_checks']['maneuver']['status']!='met' or complete['actual_native_capture'] is not False:
            raise ValueError('synthetic physical completion proof missing')
        return {'case_id':case_id,'sets':['held-out'],'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],'source_audit':result,'diagnostic_fixture':True,'actual_native_capture':False,'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--negative',action='store_true');args=parser.parse_args()
    print(json.dumps(run(args.case,args.negative),sort_keys=True))

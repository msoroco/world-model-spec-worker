"""Independent CPU delivery audit over exact-case synthetic source bundles."""
from __future__ import annotations
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
spec=importlib.util.spec_from_file_location('road_half_delivery_audit',HERE/'delivery_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def run(case_id,negative=False):
    entries=json.loads((HERE/'execution-manifest.json').read_text())['cases']
    entry=next((e for e in entries if e['case_id']==case_id),None)
    if entry is None:raise ValueError('unknown exact road-half case')
    with TemporaryDirectory(prefix='road-half-delivery-',dir=ROOT/'.runtime-work') as temp:
        base=Path(temp)/"fixture"
        materialize(ROOT,ROOT/entry['fixture_recipe'],base)
        expected=len((base/'video_frames.jsonl').read_text().splitlines())
        if negative:
            (base/'body_history.jsonl').unlink()
        measured=audit.audit_delivery(base,expected_frames=expected)
        if len(measured['camera_sources'])!=4 or not measured['source_join_complete']:
            raise ValueError('camera source audit incomplete')
        complete=json.loads((HERE/'physical'/f'{case_id.split("__")[-1]}-complete_motion.json').read_text())
        if complete['physical_checks']['maneuver']['status']!='met' or complete['actual_native_capture'] is not False:
            raise ValueError('synthetic physical outcome proof missing')
        return {'case_id':case_id,'set':'held-out','checks':['native_source','all_participants',
                'time_join','full_video_decode','actual_pixels','physical_completion'],
                'camera_sources':measured['camera_sources'],
                'physical_fixture_only':True,'actual_native_capture':False,
                'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True)
    parser.add_argument('--negative',action='store_true');args=parser.parse_args()
    print(json.dumps(run(args.case,args.negative),sort_keys=True))

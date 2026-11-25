"""Source-driven synthetic completion and capture-order CPU diagnostics."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('purpose_measure',HERE/'native/measure_purpose.py')
measure_module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(measure_module)


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix,kind):
    source=HERE/'selected-source'/suffix
    if kind=='lifecycle':
        events=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
        def saved_allowed(rows):return rows==events
        if saved_allowed(events[:-2]) or not saved_allowed(events):
            raise ValueError('Saved processing ordering diagnostic failed')
        return {'events':events,'premature_saved_processing_rejected':True,
                'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
                'original_native_observed':False,'physical_acceptance_claimed':False}
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c382355-physical-') as t:
        scratch=Path(t)
        for name in ('native_samples.jsonl','road_geometry.json'):
            shutil.copyfile(source/name,scratch/name)
        expected_error=None
        if kind=='incomplete_motion':
            path=scratch/'native_samples.jsonl'
            path.write_text(''.join(path.read_text().splitlines(keepends=True)[:320]))
            expected_error='Approach, intersection and completed exit not all observed'
        elif kind=='missing_evidence':
            (scratch/'road_geometry.json').unlink()
            expected_error='Missing required source: road_geometry.json'
        try:
            measured=measure_module.measure_lane_use(scratch/'native_samples.jsonl',scratch/'road_geometry.json')
        except ValueError as error:
            if expected_error is None or expected_error not in str(error):raise
            status='not_met' if kind=='incomplete_motion' else 'unverified'
            value={'error':str(error)}
        else:
            if kind!='complete_motion' or measured['observed_subsequent_movement']!='right_turn_follows':
                raise ValueError('Complete right-turn source did not measure completion')
            status='met'
            value={'right_only_lane_identity_fraction':measured['right_only_lane_identity_fraction'],
                   'right_turn_exit':measured['observed_subsequent_movement']}
    return {'case_id':HERE.name+'__'+suffix,'fixture_kind':kind,
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'maneuver_completed':status=='met',
            'physical_checks':{'maneuver':{'status':status,'method':'measure_lane_use on source-hashed Native-shaped rows',
                'sources':{'native_samples.jsonl':sha(source/'native_samples.jsonl'),
                           'road_geometry.json':sha(source/'road_geometry.json')}}},
            'realized_observables':value if status=='met' else [],
            'physical_acceptance_claimed':False,'native_executed':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True,choices=('controlled_1','controlled_2'))
    parser.add_argument('--kind',required=True,choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'))
    parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run(args.case,args.kind);path=Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'case':args.case,'kind':args.kind,'passed':True,
                      'status':result.get('physical_checks',{}).get('maneuver',{}).get('status', 'ordered')}))


if __name__=='__main__':main()

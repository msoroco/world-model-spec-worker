"""CPU test of original-source audit logic using explicitly simulated Native fixtures.

The fixture is scratch-only and has no evidentiary standing as a Native capture.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit_attempt

VIEWS = ('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixture(case_id, source, scratch):
    scratch.mkdir(parents=True, exist_ok=True)
    names = (['config.json','construction.json','runner.py','original-group-history.jsonl',
              'camera-frame-map.jsonl','video_frames.jsonl','caravan-context.json'] +
             [view + '.mkv' for view in VIEWS])
    for name in names:
        target = scratch / name
        if target.exists():
            target.unlink()
        os.link(source / name, target)
    context = json.loads((scratch/'caravan-context.json').read_text())
    context.update({'directed_driving_lane_id':'lane-1',
                    'weather_sha256':'cpu-test-weather-source',
                    'vehicle_blueprints_sha256':'cpu-test-blueprints-source',
                    'coordination_source':'cpu-test-authored-group-' + context['group_kind']})
    context_path = scratch/'caravan-context.json'
    context_path.unlink()
    context_path.write_text(json.dumps(context,indent=2)+'\n')
    result = json.loads((source/'result.json').read_text())
    result['diagnostic_fixture'] = False
    processed = scratch/'processed-result.json'
    processed.write_text(json.dumps(result,indent=2)+'\n')
    seal = {'format':'worker-sealed-capture','provenance_kind':'native',
            'diagnostic_fixture':False,'frames':600,
            'restoration':{'restored':True},
            'native_revision':{'construction_sha256':sha(scratch/'construction.json'),
                               'runner_sha256':sha(scratch/'runner.py')},
            'sources':{name:sha(scratch/name) for name in names if name not in ('config.json','construction.json','runner.py')}}
    (scratch/'capture-seal.json').write_text(json.dumps(seal,indent=2)+'\n')
    return processed


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--negative',action='store_true')
    args=parser.parse_args()
    suffix=args.case.removeprefix(HERE.name+'__')
    source=ROOT/'.runtime-work/c160013-1273'/('compat-'+suffix+'-primary-v3')
    if not source.is_dir():
        raise ValueError('current exact compatibility source absent')
    scratch=ROOT/'.runtime-work/c160013-1273/audit-fixtures'/suffix
    if scratch.exists():
        shutil.rmtree(scratch)
    processed=fixture(args.case,source,scratch)
    if args.negative:
        history=scratch/'original-group-history.jsonl'
        history.unlink()
        history.write_text('\n'.join((source/'original-group-history.jsonl').read_text().splitlines()[:-1])+'\n')
        try:
            audit_attempt(scratch,processed,args.case)
        except ValueError as error:
            if 'sealed Native group source changed' not in str(error):
                raise
            print('EXPECTED REJECTION: '+str(error))
            return
        raise AssertionError('changed original group history was accepted')
    result=audit_attempt(scratch,processed,args.case)
    assert result['original_frame_count']==600
    assert set(result['camera_decodes'])==set(VIEWS)
    output=ROOT/'.runtime-work/c160013-1273/audit-results'/('audit-'+suffix+'.json')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('CPU-TEST ONLY positive original-source audit logic: '+args.case)


if __name__=='__main__':
    main()

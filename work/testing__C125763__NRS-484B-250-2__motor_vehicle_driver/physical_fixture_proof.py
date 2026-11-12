"""Synthetic CPU tests of C125763 physical classification and closure order."""
import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.common import sha
from worker_exchange.native_output import physical_result,seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release


def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')


def fixture_sources(root,entry):
    construction=read(ROOT/entry['construction'])
    config=json.loads(next(row['content'] for row in construction['files']
                           if row['path']=='config.json'))
    if config.get('physical_completion', {}).get('body_key') != 'ego.body_vertices_xy_m':
        raise ValueError('Construction lacks original body-history criterion')
    write(root/'config.json',config)
    recipe=read(REPO/entry['fixture_recipe'])
    source=REPO/recipe['generator']['source']
    if sha(source)!=recipe['generator']['sha256']:
        raise ValueError('Changed diagnostic source')
    source_files=read(source)['files']
    for name in ('trace.jsonl','video_frames.jsonl','crossing_history.jsonl'):
        (root/name).write_text(source_files[name])
    write(root/'acquisition-provenance.json',{
        'provenance_kind':'native','diagnostic_fixture':True,
        'scope':'Synthetic CPU physical-classifier fixture only'})
    return construction


def motion(entry,kind,output):
    with tempfile.TemporaryDirectory(prefix='c125763-physical-') as temporary:
        root=Path(temporary)
        fixture_sources(root,entry)
        source=root/'crossing_history.jsonl'
        if kind=='missing_evidence':
            source.unlink()
        else:
            rows=[json.loads(line) for line in source.read_text().splitlines()]
            if kind=='complete_motion':
                for i,row in enumerate(rows[32:],32):
                    dx=.5*(i-31)
                    row['ego']['body_vertices_xy_m']=[[x+dx,y] for x,y in
                        row['ego']['body_vertices_xy_m']]
            else:
                first=copy.deepcopy(rows[0]['ego']['body_vertices_xy_m'])
                for row in rows:row['ego']['body_vertices_xy_m']=copy.deepcopy(first)
            source.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))
        result=physical_result(root,{'target_checks':[]})
        expected={'complete_motion':'met','incomplete_motion':'not_met',
                  'missing_evidence':'unverified'}[kind]
        check=result['physical_checks']['maneuver']
        if check['status']!=expected or result['maneuver_completed']!=(expected=='met'):
            raise ValueError('Physical classifier differed: '+check['status']+' expected '+expected)
        if not check['sources'] or not check['method']:
            raise ValueError('Physical classifier lacks original-frame source audit')
        if result['diagnostic_fixture'] is not True or result['physical_acceptance_claimed'] is not False:
            raise ValueError('Synthetic fixture claimed physical acceptance')
        if kind=='missing_evidence' and 'crossing_history.jsonl' not in check['missing_evidence']:
            raise ValueError('Missing original body history not reported')
        write(output,result)
        print(json.dumps({'case_id':entry['case_id'],'fixture':kind,
                          'maneuver_status':check['status'],'diagnostic_fixture':True}))


def lifecycle(entry,output):
    saved_name={'yield_ego_left_near_time':'promoted-primary-primary-saved-receipt.json',
                'yield_ego_right_near_time':'promoted-right-primary-saved-receipt.json',
                'yield_ego_left_separated':'promoted-separated-primary-saved-receipt.json',
                'yield_opposite_left_turn':'promoted-opposite-primary-saved-receipt.json'}
    suffix=entry['case_id'].split('__')[-1]
    saved_path=ROOT/saved_name[suffix]
    saved=read(saved_path)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('case_id')!=entry['case_id'] or
            saved['analysis_revision']['construction_sha256']!=entry['construction_sha256']):
        raise ValueError('Current selected recorded-only saved receipt missing')
    with tempfile.TemporaryDirectory(prefix='c125763-lifecycle-') as temporary:
        root=Path(temporary)
        construction=fixture_sources(root,entry)
        write(root/'construction.json',construction)
        (root/'runner.py').write_text(next(row['content'] for row in construction['files']
                                        if row['path']=='runner.py'))
        try:
            seal_capture(root,frames=60,restoration={'restored':True},errors=[],
                         encoder_exit_codes={'fixture_encoder':1},context={'diagnostic_fixture':True})
        except ValueError as error:
            if 'unclosed/failed encoders' not in str(error):raise
        else:raise ValueError('Failed fixture encoder was sealed')
        seal=seal_capture(root,frames=60,restoration={'restored':True},errors=[],
                          encoder_exit_codes={'fixture_encoder':0},context={'diagnostic_fixture':True})
        try:
            acknowledge_owner_release(root,root/'owner-release.json',True)
        except ValueError as error:
            if 'Native process has not exited' not in str(error):raise
        else:raise ValueError('Owner release preceded Native exit')
        native=record_native_exit(root)
        owner=acknowledge_owner_release(root,root/'owner-release.json',True)
        events=seal['events']+[native['event'],owner['event'],saved['events'][0]]
        expected=['capture_finished','encoders_closed','restoration_verified',
                  'native_exit','owner_released','saved_processing_started']
        if events!=expected:raise ValueError('Saved processing preceded verified closure')
        write(output,{'events':events,'diagnostic_fixture':True,'fixture_frames':60,
                      'failed_encoder_rejected':True,'premature_release_rejected':True,
                      'capture_seal_sha256':sha(root/'capture-seal.json'),
                      'native_exit_sha256':sha(root/'native-exit.json'),
                      'owner_release_sha256':sha(root/'owner-release.json'),
                      'saved_processing_receipt_sha256':sha(saved_path)})
        print(json.dumps({'case_id':entry['case_id'],'events':events,
                          'diagnostic_fixture':True}))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True,type=Path)
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',required=True,choices=(
        'complete_motion','incomplete_motion','missing_evidence','lifecycle'))
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    entry=next((item for item in read(args.manifest)['cases']
                if item['case_id']==args.case),None)
    if entry is None:raise ValueError('Unknown exact physical fixture case')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.kind=='lifecycle':lifecycle(entry,args.output)
    else:motion(entry,args.kind,args.output)


if __name__=='__main__':main()

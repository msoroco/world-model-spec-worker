"""Exercise pinned source-bound motion and lifecycle checks with CPU diagnostics.

These inputs are synthetic, explicitly marked diagnostic, and cannot verify an
actual CARLA capture, source-camera visibility, or a legal judgment.
"""
import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result,seal_capture
from worker_exchange.saved_processing import record_native_exit,acknowledge_owner_release
from worker_exchange.common import sha

def read(path):return json.loads(Path(path).read_text())
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')

def exercise(entry,folder,kind,output):
    construction=read(folder/entry['construction'])
    config=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    recipe=read(REPO/entry['fixture_recipe'])
    diagnostic=read(REPO/recipe['generator']['source'])
    with tempfile.TemporaryDirectory(prefix='c101303-physical-fixture-') as temp:
        stage=Path(temp)
        (stage/'config.json').write_text(json.dumps(config)+'\n')
        for name in ('trace.jsonl','video_frames.jsonl','road_context.json','vehicle_history.jsonl'):
            (stage/name).write_text(diagnostic['files'][name])
        write(stage/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':True,
             'scope':'Synthetic Native-shaped CPU classifier fixture; no physical acquisition'})
        if kind=='incomplete_motion':
            rows=[json.loads(s) for s in (stage/'vehicle_history.jsonl').read_text().splitlines()]
            for row in rows:row['ego']['lane_id']=config['physical_completion']['destination_lane']+1
            (stage/'vehicle_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
        elif kind=='missing_evidence':(stage/'vehicle_history.jsonl').unlink()
        result=physical_result(stage,{'target_checks':[],'realized_observables':{},
                'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False})
        expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        actual=result['physical_checks']['maneuver']['status']
        if actual!=expected:raise ValueError('Pinned physical classifier returned '+actual+'; expected '+expected)
        if result['diagnostic_fixture'] is not True or result['physical_acceptance_claimed'] is not False:
            raise ValueError('CPU fixture provenance was not preserved')
        write(output,result)
        print(json.dumps({'case_id':entry['case_id'],'fixture':kind,'status':actual,
                          'diagnostic_fixture':True,'source_hashes':result['physical_checks']['maneuver']['sources']}))

def lifecycle(entry,folder,output,saved_override=None):
    construction=read(folder/entry['construction'])
    saved=Path(saved_override).resolve() if saved_override else folder/(
        'primary-saved-processing.json' if entry['construction']=='construction.json' else
        'cases/'+entry['case_id'].rsplit('source_verified_',1)[-1]+'/primary-saved-processing.json')
    if not saved_override and not saved.is_file():
        saved=folder/'cases'/('source_verified_'+entry['case_id'].rsplit('source_verified_',1)[-1])/'primary-saved-processing.json'
    receipt=read(saved)
    if (receipt.get('format')!='worker-saved-processing' or receipt.get('passed') is not True
            or receipt.get('recorded_only') is not True or receipt['analysis_revision']['construction_sha256']!=entry['construction_sha256']):
        raise ValueError('Current selected saved-only diagnostic proof missing')
    with tempfile.TemporaryDirectory(prefix='c101303-lifecycle-fixture-') as temp:
        stage=Path(temp)
        write(stage/'construction.json',construction)
        runner=next(f['content'] for f in construction['files'] if f['path']=='runner.py')
        (stage/'runner.py').write_text(runner)
        (stage/'trace.jsonl').write_text('{"frame":1,"time_s":0.05}\n')
        (stage/'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
        write(stage/'acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':True,
              'scope':'Synthetic lifecycle CPU fixture only'})
        dummy_owner=io.StringIO('fixture resource')
        dummy_owner.close()
        if not dummy_owner.closed:raise ValueError('Fixture resource owner was not released')
        seal=seal_capture(stage,frames=1,restoration={'restored':True,'fixture_only':True},errors=[],
                          encoder_exit_codes={'fixture_encoder':0},context={'diagnostic_fixture':True})
        exited=record_native_exit(stage)
        released=acknowledge_owner_release(stage,stage/'owner-release.json',True)
        if exited['capture_seal_sha256']!=sha(stage/'capture-seal.json') or released['native_exit_sha256']!=sha(stage/'native-exit.json'):
            raise ValueError('Lifecycle digest join failed')
        events=seal['events']+[exited['event'],released['event'],receipt['events'][0]]
        expected=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
        if events!=expected:raise ValueError('Lifecycle event ordering differs')
        write(output,{'events':events,'diagnostic_fixture':True,'saved_processing_receipt_sha256':sha(saved),
                      'capture_seal_sha256':sha(stage/'capture-seal.json'),
                      'native_exit_sha256':sha(stage/'native-exit.json'),
                      'owner_release_sha256':sha(stage/'owner-release.json')})
        print(json.dumps({'case_id':entry['case_id'],'events':events,'diagnostic_fixture':True}))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--saved-receipt')
    args=parser.parse_args();manifest=Path(args.manifest).resolve();folder=manifest.parent
    entry=next(e for e in read(manifest)['cases'] if e['case_id']==args.case)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    if args.kind=='lifecycle':lifecycle(entry,folder,output,args.saved_receipt)
    else:exercise(entry,folder,args.kind,output)
if __name__=='__main__':main()

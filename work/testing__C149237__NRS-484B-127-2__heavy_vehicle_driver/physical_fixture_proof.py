"""Exercise pinned truck motion and ownership checkers with CPU-only sources.

Every fixture is diagnostic. A Native-shaped provenance marker tests the
classifier interface and never represents a CARLA acquisition.
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha


def read(path):
    return json.loads(Path(path).read_text())


def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_rows(path,values):
    Path(path).write_text(''.join(json.dumps(v,allow_nan=False)+'\n' for v in values))


def fixture(entry, kind, output):
    suffix=entry['case_id'].split('__')[-1]
    version = 'v17' if suffix == 'gap_below_500ft' else 'v16'
    source=ROOT/'.runtime-work'/f'c149237-{suffix}-saved-{version}/v0001/analysis'
    with tempfile.TemporaryDirectory(prefix='c149237-physical-') as temporary:
        stage=Path(temporary)
        for name in ('config.json','truck_history.jsonl','video_frames.jsonl',
                     'trace.jsonl','road_context.json'):
            (stage/name).write_bytes((source/name).read_bytes())
        cfg=read(stage/'config.json')
        if not cfg.get('physical_completion') or cfg['selected_case_id']!=entry['case_id']:
            raise ValueError('Current exact physical descriptor missing')
        write(stage/'acquisition-provenance.json',{
            'provenance_kind':'native','diagnostic_fixture':True,
            'scope':'Native-shaped synthetic classifier fixture; no CARLA acquisition'})
        if kind=='complete_motion' and suffix!='overtaking':
            motion=rows(stage/'truck_history.jsonl')
            for index,row in enumerate(motion):
                for role in ('ego','lead'):
                    row[role]['body_vertices_xy_m']=[
                        [point[0]+3*index,point[1]]
                        for point in row[role]['body_vertices_xy_m']]
            write_rows(stage/'truck_history.jsonl',motion)
        elif kind=='incomplete_motion' and suffix=='overtaking':
            motion=rows(stage/'truck_history.jsonl')
            for row in motion:
                body=row['ego']['body_vertices_xy_m']
                shift=-1.9-(min(point[1] for point in body)+max(point[1] for point in body))/2
                row['ego']['body_vertices_xy_m']=[[point[0],point[1]+shift] for point in body]
            write_rows(stage/'truck_history.jsonl',motion)
        elif kind=='missing_evidence':
            (stage/'truck_history.jsonl').unlink()
        elif kind not in ('complete_motion','incomplete_motion'):
            raise ValueError('Unknown physical fixture kind')
        result=physical_result(stage,{'target_checks':[], 'realized_observables':{},
                'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False})
        expected={'complete_motion':'met','incomplete_motion':'not_met',
                  'missing_evidence':'unverified'}[kind]
        status=result['physical_checks']['maneuver']['status']
        if status!=expected or result.get('diagnostic_fixture') is not True or result.get('physical_acceptance_claimed') is not False:
            raise ValueError(f'Physical fixture {kind}: expected {expected}, got {status}')
        write(output,result)
        print(json.dumps({'case_id':entry['case_id'],'kind':kind,'status':status,
                          'diagnostic_fixture':True,'physical_acceptance_claimed':False},sort_keys=True))


def lifecycle(entry,output):
    suffix=entry['case_id'].split('__')[-1]
    folder=Path(__file__).resolve().parent
    saved=read(folder/(suffix+'-saved-processing.json'))
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('native_revision',{}).get('construction_sha256')!=entry['construction_sha256']):
        raise ValueError('Current exact saved-processing proof missing')
    construction=read(folder/entry['construction'])
    with tempfile.TemporaryDirectory(prefix='c149237-lifecycle-') as temporary:
        stage=Path(temporary)
        write(stage/'construction.json',construction)
        runner=next(item['content'] for item in construction['files'] if item['path']=='runner.py')
        (stage/'runner.py').write_text(runner)
        (stage/'trace.jsonl').write_text('{"frame":1,"time_s":0.05}\n')
        (stage/'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
        write(stage/'acquisition-provenance.json',{'provenance_kind':'native',
              'diagnostic_fixture':True,'scope':'Synthetic lifecycle CPU fixture only'})
        seal=seal_capture(stage,frames=1,restoration={'restored':True,'fixture_only':True},
                          errors=[],encoder_exit_codes={'fixture_encoder':0},
                          context={'diagnostic_fixture':True})
        exited=record_native_exit(stage)
        released=acknowledge_owner_release(stage,stage/'owner-release.json',True)
        if exited['capture_seal_sha256']!=sha(stage/'capture-seal.json') or released['native_exit_sha256']!=sha(stage/'native-exit.json'):
            raise ValueError('Lifecycle source digest join failed')
        events=seal['events']+[exited['event'],released['event'],saved['events'][0]]
        expected=['capture_finished','encoders_closed','restoration_verified',
                  'native_exit','owner_released','saved_processing_started']
        if events!=expected:
            raise ValueError('Saved processing preceded Native owner release')
        write(output,{'events':events,'diagnostic_fixture':True,
                      'saved_processing_sha256':sha(folder/(suffix+'-saved-processing.json')),
                      'capture_seal_sha256':sha(stage/'capture-seal.json'),
                      'native_exit_sha256':sha(stage/'native-exit.json'),
                      'owner_release_sha256':sha(stage/'owner-release.json')})
        print(json.dumps({'case_id':entry['case_id'],'events':events,
                          'diagnostic_fixture':True},sort_keys=True))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    entry=next(row for row in read(args.manifest)['cases'] if row['case_id']==args.case)
    if args.kind=='lifecycle':lifecycle(entry,args.output)
    else:fixture(entry,args.kind,args.output)


if __name__=='__main__':
    main()

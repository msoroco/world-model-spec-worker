"""CPU-only C109749 source-bound turn and capture lifecycle fixtures.

Synthetic Native-shaped data tests code paths. It is never physical acceptance.
"""
import argparse
import io
import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result, seal_capture
from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release
from worker_exchange.common import sha


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def motion(entry, folder, kind, output):
    construction = read(folder/entry['construction'])
    config = json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
    recipe = read(REPO/entry['fixture_recipe'])
    diagnostic = read(REPO/recipe['generator']['source'])['files']
    with tempfile.TemporaryDirectory(prefix='c109749-physical-') as temp:
        root = Path(temp)
        write(root/'config.json', config)
        for name in ('trace.jsonl','video_frames.jsonl','interaction_history.jsonl','intersection_geometry.json'):
            (root/name).write_text(diagnostic[name])
        write(root/'acquisition-provenance.json', {'provenance_kind':'native',
              'diagnostic_fixture':True,'scope':'Synthetic CPU classifier fixture only'})
        if kind == 'incomplete_motion':
            rows = [json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines()]
            for row in rows:
                row['ego_heading_deg'] = rows[0]['ego_heading_deg']
            (root/'interaction_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
        elif kind == 'missing_evidence':
            (root/'interaction_history.jsonl').unlink()
        result = physical_result(root, {'target_checks':[], 'realized_observables':{},
                'setup_confirmed':False,'behavior_attempted':False,'maneuver_completed':False})
        expected = {'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
        actual = result['physical_checks']['maneuver']['status']
        if actual != expected or result['maneuver_completed'] != (expected == 'met'):
            raise ValueError(f'Physical classifier mismatch: {actual}, expected {expected}')
        if result['diagnostic_fixture'] is not True or result['physical_acceptance_claimed'] is not False:
            raise ValueError('Synthetic provenance or acceptance flag changed')
        write(output, result)
        print(json.dumps({'case_id':entry['case_id'],'fixture':kind,'status':actual,
                          'diagnostic_fixture':True,'source_hashes':result['physical_checks']['maneuver']['sources']}))


def lifecycle(entry, folder, output):
    construction = read(folder/entry['construction'])
    saved = (folder/'primary-saved-processing.json' if entry['construction']=='construction.json'
             else (folder/entry['construction']).parent/'primary-saved-processing.json')
    receipt = read(saved)
    if (receipt.get('format') != 'worker-saved-processing' or receipt.get('passed') is not True
            or receipt.get('recorded_only') is not True
            or receipt['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Current primary saved-processing proof missing')
    with tempfile.TemporaryDirectory(prefix='c109749-lifecycle-') as temp:
        root = Path(temp)
        write(root/'construction.json', construction)
        (root/'runner.py').write_text(next(f['content'] for f in construction['files'] if f['path']=='runner.py'))
        (root/'trace.jsonl').write_text('{"frame":1,"time_s":0.05}\n')
        (root/'video_frames.jsonl').write_text('{"video_frame":0,"carla_frame":1,"time_s":0.05}\n')
        write(root/'acquisition-provenance.json', {'provenance_kind':'native',
              'diagnostic_fixture':True,'scope':'Synthetic lifecycle fixture only'})
        resource = io.StringIO('fixture camera resource')
        resource.close()
        if not resource.closed:
            raise ValueError('Fixture camera resource remains open')
        seal = seal_capture(root, frames=1, restoration={'restored':True,'fixture_only':True},
                            errors=[],encoder_exit_codes={'fixture_encoder':0},context={'diagnostic_fixture':True})
        exited = record_native_exit(root)
        released = acknowledge_owner_release(root,root/'owner-release.json',True)
        if exited['capture_seal_sha256'] != sha(root/'capture-seal.json') or released['native_exit_sha256'] != sha(root/'native-exit.json'):
            raise ValueError('Capture lifecycle hash join failed')
        events = seal['events']+[exited['event'],released['event'],receipt['events'][0]]
        expected = ['capture_finished','encoders_closed','restoration_verified','native_exit',
                    'owner_released','saved_processing_started']
        if events != expected:
            raise ValueError('Capture lifecycle ordering differs')
        write(output, {'events':events,'diagnostic_fixture':True,
              'saved_processing_receipt_sha256':sha(saved),
              'capture_seal_sha256':sha(root/'capture-seal.json'),
              'native_exit_sha256':sha(root/'native-exit.json'),
              'owner_release_sha256':sha(root/'owner-release.json')})
        print(json.dumps({'case_id':entry['case_id'],'events':events,'diagnostic_fixture':True}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--case',required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence','lifecycle'),required=True)
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    manifest = Path(args.manifest).resolve()
    entry = next(x for x in read(manifest)['cases'] if x['case_id']==args.case)
    output = Path(args.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    if args.kind=='lifecycle':
        lifecycle(entry,manifest.parent,output)
    else:
        motion(entry,manifest.parent,args.kind,output)


if __name__=='__main__':
    main()

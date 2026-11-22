"""Portable source-shaped recipes for the nine exact C179480 sweep drafts."""
import hashlib
import json
import shutil
from pathlib import Path

from build_reference_recipe import build as build_recipe
from sweep_case import SWEEPS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
STAGE = ROOT/'.runtime-work/c179480-native-sweep/staged'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def trace_rows(rows, mapping, actor_hash):
    output = []
    for actor, frame in zip(rows, mapping):
        output.append({
            'frame':actor['frame'],'time_s':frame['time_s'],
            'position_m':[actor['ego_x_m'],actor['ego_y_m']],
            'position':{'x':actor['ego_x_m'],'y':actor['ego_y_m'],'z':0.0},
            'heading_deg':actor['ego_yaw_deg'],
            'speed_mps':actor['ego_speed_mps'],
            'speed_mph':actor['ego_speed_mps']/.44704,
            'velocity_mps':actor['ego_velocity_xyz_mps'],'control':{},
            'speed_provenance':'synthetic_native_sample',
            'source_actor_sha256':actor_hash,
        })
    return ''.join(json.dumps(row,allow_nan=False)+'\n' for row in output)


def source_for(sweep_id, value):
    if sweep_id == 'c179480-traffic-effect-gap':
        return ROOT/'.runtime-work/c179480-traffic-effect-sweep'/('gap-'+str(value).replace('.','_'))
    if sweep_id == 'c179480-safe-operation-gap':
        return ROOT/'.runtime-work/c179480-safe-operation-sweep'/('gap-'+str(value).replace('.','_'))
    if sweep_id == 'c179480-governing-red-onset':
        return ROOT/'.runtime-work/c179480-governing-law-sweep'/('onset-'+str(round(value*20)))
    raise ValueError('Unknown source-shaped sweep')


def build():
    construction_manifest=json.loads((HERE/'sweep-primary-manifest.json').read_text())
    canonical=json.loads((HERE/'proposals/canonical-cases.json').read_text())
    semantics={HERE.name+'__'+case['case_id']:case for case in canonical['cases'] if case.get('sweep_id')}
    entries=[]
    for item in construction_manifest['cases']:
        cid=item['case_id'];case=semantics[cid];sweep_id=case['sweep_id']
        base,axis,_=SWEEPS[sweep_id];value=case['sweep_point'][axis]
        source=source_for(sweep_id,value)
        if not (source/'native-actors.jsonl').is_file():
            raise ValueError('Source-shaped sweep probe must be built first: '+cid)
        staged=STAGE/cid;staged.mkdir(parents=True,exist_ok=True)
        for name in ('native-actors.jsonl','video_frames.jsonl'):
            shutil.copyfile(source/name,staged/name)
        base_source=HERE/('fixtures/'+base+'-sources')
        shutil.copyfile(base_source/'acquisition-provenance.json',staged/'acquisition-provenance.json')
        readback=json.loads((base_source/'native-map-readback.json').read_text())
        readback.update(sweep_axis=axis,sweep_value=value)
        write(staged/'native-map-readback.json',readback)
        rows=[json.loads(line) for line in (staged/'native-actors.jsonl').read_text().splitlines()]
        mapping=[json.loads(line) for line in (staged/'video_frames.jsonl').read_text().splitlines()]
        if len(rows)!=600 or len(mapping)!=600 or any(
                row['frame']!=frame['carla_frame'] for row,frame in zip(rows,mapping)):
            raise ValueError('Synthetic sweep source/frame join changed: '+cid)
        (staged/'trace.jsonl').write_text(trace_rows(rows,mapping,sha(staged/'native-actors.jsonl')))
        recipe_result=build_recipe(staged,base,case_id=cid)
        contract=json.loads((HERE/('draft-'+base+'-measurement-contract.json')).read_text())
        contract['case_id']=cid
        contract_path=HERE/('sweep-'+cid+'-measurement-contract.json')
        write(contract_path,contract)
        construction=HERE/item['construction']
        if sha(construction)!=item['construction_sha256']:
            raise ValueError('Sweep construction changed: '+cid)
        entries.append({'case_id':cid,'construction':item['construction'],
                        'construction_sha256':item['construction_sha256'],
                        'fixture_recipe':str((HERE/('draft-'+cid+'-diagnostic-recipe.json')).relative_to(ROOT)),
                        'measurement_contract':contract_path.name,
                        'measurement_procedure':{'entrypoint':'native_finalize.py'}})
    if len(entries)!=9:
        raise ValueError('Nine exact sweep diagnostic recipes required')
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':construction_manifest['runtime_manifest_sha256'],
              'status':'draft_sweep_primary_compatibility_diagnostic',
              'cases':entries}
    target=HERE/'sweep-primary-compatibility-manifest.json';write(target,manifest)
    return {'manifest':target.name,'manifest_sha256':sha(target),'cases':len(entries)}


if __name__=='__main__':
    print(json.dumps(build(),indent=2,sort_keys=True))

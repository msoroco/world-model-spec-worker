"""Bind current exact C229410 diagnostic cases for public compatibility."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')


def build():
    draft=json.loads((HERE/'draft-native-manifest.json').read_text())
    cases=[]
    for index,entry in enumerate(draft['cases']):
        suffix=entry['case_id'].rsplit('__',1)[-1]
        contract={'format':'worker-measurement-contract','case_id':entry['case_id'],
            'requirements':[{'disposition_index':0,'requirement':'NRS-484B-450-1j',
                'source':'NRS 484B.450(1)(j)','output_key':'fire_station_entrance_observation',
                'method':'fire_station_entrance_observation','value_type':'object','kind':'measured',
                'inputs':['entrance-context.json','native-vehicle.jsonl','video_frames.jsonl','road.xodr']}],
            'negative':{'remove':['entrance-context.json'],
                'error_contains':'Missing required source: entrance-context.json'}}
        write(HERE/('measurement-'+suffix+'.json'),contract)
        config=json.loads(next(f['content'] for f in json.loads((HERE/entry['construction']).read_text())['files'] if f['path']=='config.json'))
        entry.update(kind='delivery',measurement_contract='measurement-'+suffix+'.json',
            measurement_procedure={'entrypoint':'finalize.py','output_schema':'c229410-parking-analysis-v1'},
            fixture_recipe='work/'+ASSIGNMENT+'/selected-recipe-'+suffix+'.json',
            native_handoff={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST',
                'port_env_var':'CARLA_PORT'},
            acquisition={'parking_geometry':{'entrypoint':'runner.py',
                'method':'same-tick original Native full body and speed readback',
                'evidence':'native-vehicle.jsonl and video_frames.jsonl'}},
            candidate_risk={'status':'none','reason':'One simple straight parking approach; no separate engineering fallback established'},
            candidates=[])
        cases.append({'case_id':entry['case_id'],'target_law_id':'NRS-484B-450-1j',
            'target_type':'judgment_sweep','rationale':'Source-shaped same-side fire-station entrance parking distance',
            'recording_description':config['recording_description'],
            'variable_assignments':{'entrance_body_edge_gap_m':{'kind':'subject_behavior',
                'value':12 if index==0 else 0}},'unresolved_judgment_calls':[
                'actual station identity and entrance','statutory distance reference method',
                'parking activity and exceptions']})
    manifest={'format':'worker-execution-manifest','assignment_id':ASSIGNMENT,
        'runtime_manifest_sha256':sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
        'status':'partial','cases':draft['cases']}
    write(HERE/'execution-manifest.json',manifest)
    write(HERE/'proposals/cases.json',{'cell_id':'C229410','actor':'motor_vehicle_driver',
        'status':'draft','cases':cases})
    return {'cases':len(cases),'manifest_sha256':sha(HERE/'execution-manifest.json')}


if __name__=='__main__':print(json.dumps(build()))

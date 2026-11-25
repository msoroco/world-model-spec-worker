"""Build subsection (4) qualifying-category request pair without claiming status."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
SOURCE=HERE/'numeric-boundary'/'numeric_1_2'/'primary'/'construction.json'
OUT=HERE/'subsection-4'
CATEGORIES={'exception_5_1':'tow_car','exception_5_2':'ordinary_vehicle'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def encoded(value):return json.dumps(value,indent=2,allow_nan=False)+'\n'

def build():
    base=json.loads(SOURCE.read_text())
    entries=[]
    for suffix,category in CATEGORIES.items():
        case_id=CASE.name+'__'+suffix
        construction=json.loads(json.dumps(base))
        construction['case_id']=case_id
        construction['status']='subsection4_category_request_cpu_draft_physical_unverified'
        files={item['path']:item for item in construction['files']}
        for item in construction['files']:
            if item['path'] not in ('assignment-source.json','case-plan.json'):
                item['content']=item['content'].replace('__numeric_1_2','__'+suffix)
        rows=[]
        for line in files['requested-tracks.jsonl']['content'].splitlines():
            row=json.loads(line)
            row['requested_vehicle_category']=category
            row['vehicle_category_verified']=False
            rows.append(row)
        files['requested-tracks.jsonl']['content']=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
        check=files['check.py']['content']
        check=check.replace("[cfg['assignment_id']+'__numeric_1_'+str(i) for i in range(3)]",
            "[cfg['assignment_id']+'__exception_5_1',cfg['assignment_id']+'__exception_5_2']")
        check=check.replace("distance = {'numeric_1_0':60.86,'numeric_1_1':60.96,'numeric_1_2':61.06}[cfg['case_id'].split('__')[-1]]",
            "distance = 61.06\n    category = 'tow_car' if cfg['case_id'].endswith('__exception_5_1') else 'ordinary_vehicle'\n    if cfg['requested_vehicle_category'] != category or cfg['vehicle_category_verified'] is not False:\n        raise ValueError('Unverified vehicle category request differs')")
        check=check.replace("                row['requested_excursion_m']==distance and",
            "                row['requested_excursion_m']==distance and\n                row['requested_vehicle_category']==category and\n                row['vehicle_category_verified'] is False and")
        files['check.py']['content']=check
        files['saved.py']['content']=files['saved.py']['content'].replace(
            "('__numeric_1_0','__numeric_1_1','__numeric_1_2')",
            "('__exception_5_1','__exception_5_2')")
        files['saved.py']['content']=files['saved.py']['content'].replace(
            "            'unmarked_pavement_reviewed': False,\n",
            "            'unmarked_pavement_reviewed': False,\n"
            "            'observed_actor_blueprint': native[0]['ego']['blueprint'],\n"
            "            'qualifying_vehicle_category_verified': False,\n")
        files['finalize.py']['content']=files['finalize.py']['content'].replace(
            "('__numeric_1_0', '__numeric_1_1', '__numeric_1_2')",
            "('__exception_5_1', '__exception_5_2')")
        files['finalize.py']['content']=files['finalize.py']['content'].replace(
            "        'statutory_200ft_verdict')}",
            "        'statutory_200ft_verdict', 'observed_actor_blueprint',\n"
            "        'qualifying_vehicle_category_verified')}")
        cfg=json.loads(files['config.json']['content'])
        cfg['case_id']=case_id;cfg['selected_case_id']=case_id;cfg['case']={'case_id':case_id}
        cfg['supported_case_ids']=[CASE.name+'__'+name for name in CATEGORIES]
        cfg['requested_vehicle_category']=category
        cfg['vehicle_category_verified']=False
        cfg['tracks_sha256']=hashlib.sha256(files['requested-tracks.jsonl']['content'].encode()).hexdigest()
        files['config.json']['content']=encoded(cfg)
        contract=json.loads(files['measurement-contract.json']['content'])
        contract['case_id']=case_id
        contract['requirements'][0]['disposition_index']=5
        contract['requirements'][0]['output_key']='subsection4_vehicle_category_source_observation'
        files['measurement-contract.json']['content']=encoded(contract)
        construction['recording_description']['limitations'].append(
            'The qualifying vehicle category is an authored request; source verification and legal exemption remain unresolved.')
        path=OUT/suffix/'primary'/'construction.json'
        put(path,construction)
        put(OUT/suffix/'measurement-contract.json',contract)
        entries.append({'case_id':case_id,'kind':'delivery','construction':suffix+'/primary/construction.json',
            'construction_sha256':sha(path),'measurement_contract':suffix+'/measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py'},'candidate_risk':{'status':'physical',
            'reason':'Vehicle qualification, original shoulder passage and statutory conditions need source review.'},
            'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
    runtime=json.loads((ROOT/'batch.json').read_text())['runtime']['root']
    manifest={'format':'worker-execution-manifest','assignment_id':CASE.name,
        'runtime_manifest_sha256':sha(ROOT/runtime/'SOURCE-MANIFEST.json'),
        'status':'subsection4_cpu_draft_only','delivery_ready':False,
        'original_native_observed':False,'cases':entries}
    put(OUT/'manifest.json',manifest)
    return {'manifest_sha256':sha(OUT/'manifest.json'),'cases':len(entries)}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))

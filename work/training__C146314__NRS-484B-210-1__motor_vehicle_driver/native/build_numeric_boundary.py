"""Build three exact 200-foot neighboring source requests from the C1 profile."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
SOURCE=HERE/'current-c1'/'exception_3_1'/'primary'/'construction.json'
OUT=HERE/'numeric-boundary'
DISTANCES={'numeric_1_0':60.86,'numeric_1_1':60.96,'numeric_1_2':61.06}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def encoded(value):return json.dumps(value,indent=2,allow_nan=False)+'\n'


def build():
    base=json.loads(SOURCE.read_text())
    entries=[]
    for suffix,distance in DISTANCES.items():
        case_id=CASE.name+'__'+suffix
        construction=json.loads(json.dumps(base))
        construction['case_id']=case_id
        construction['status']='numeric_boundary_cpu_draft_physical_unverified'
        files={item['path']:item for item in construction['files']}
        for item in construction['files']:
            if item['path'] not in ('assignment-source.json','case-plan.json'):
                item['content']=item['content'].replace('__exception_3_1','__'+suffix)
        rows=[]
        for i in range(600):
            t=(i+1)/20;x=5+8*t
            blend=max(0,min(1,(x-17.5)/5,(20+distance+2.5-x)/5))
            y=round(-1.75-3.5*blend,6)
            rows.append({'frame':i,'time_s':t,'case_id':case_id,'candidate_id':'primary',
                'source_kind':'authored_native_request','road_id':210,'ego_x_m':round(x,6),
                'ego_y_m':y,'ego_lane_id':-2 if y < -3.5 else -1,
                'lead_x_m':round(35+4*t,6),'lead_y_m':-1.75,'lead_lane_id':-1,
                'requested_excursion_m':distance,'unmarked_pavement_verified':False,
                'one_way_designation_verified':False,'unobstructed_pavement_verified':False,
                'actual_right_pass_observed':False,'legal_verdict':None})
        files['requested-tracks.jsonl']['content']=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
        check=files['check.py']['content']
        start=check.index("    if (cfg['assignment_id']")
        end=check.index("        raise ValueError('Assignment identity differs')",start)
        check=check[:start]+"    if (cfg['assignment_id'] != assignment['assignment_id'] or\n            cfg['assignment_id'] != plan['assignment_id'] or\n            cfg['case_id'] not in [cfg['assignment_id']+'__numeric_1_'+str(i) for i in range(3)]):\n"+check[end:]
        check=check.replace("distance = 61.06 if cfg['case_id'].endswith('exception_3_1') else 60.96",
            "distance = {'numeric_1_0':60.86,'numeric_1_1':60.96,'numeric_1_2':61.06}[cfg['case_id'].split('__')[-1]]")
        files['check.py']['content']=check
        saved=files['saved.py']['content'].replace("('__exception_3_1','__exception_3_2')",
            "('__numeric_1_0','__numeric_1_1','__numeric_1_2')")
        files['saved.py']['content']=saved
        final=files['finalize.py']['content'].replace("('__exception_3_1', '__exception_3_2')",
            "('__numeric_1_0', '__numeric_1_1', '__numeric_1_2')")
        files['finalize.py']['content']=final
        cfg=json.loads(files['config.json']['content'])
        cfg['case_id']=case_id;cfg['selected_case_id']=case_id;cfg['case']={'case_id':case_id}
        cfg['supported_case_ids']=[CASE.name+'__'+name for name in DISTANCES]
        cfg['requested_excursion_m']=distance
        cfg['tracks_sha256']=hashlib.sha256(files['requested-tracks.jsonl']['content'].encode()).hexdigest()
        files['config.json']['content']=encoded(cfg)
        contract=json.loads(files['measurement-contract.json']['content'])
        contract['case_id']=case_id
        contract['requirements'][0]['disposition_index']=6
        contract['requirements'][0]['output_key']='numeric_200ft_source_observation'
        files['measurement-contract.json']['content']=encoded(contract)
        path=OUT/suffix/'primary'/'construction.json'
        put(path,construction)
        put(OUT/suffix/'measurement-contract.json',contract)
        entries.append({'case_id':case_id,'kind':'delivery','construction':suffix+'/primary/construction.json',
            'construction_sha256':sha(path),'measurement_contract':suffix+'/measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py'},'candidate_risk':{'status':'physical',
            'reason':'Actual unmarked pavement, source span and legal result need independent review.'},
            'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
    runtime=json.loads((ROOT/'batch.json').read_text())['runtime']['root']
    manifest={'format':'worker-execution-manifest','assignment_id':CASE.name,
        'runtime_manifest_sha256':sha(ROOT/runtime/'SOURCE-MANIFEST.json'),
        'status':'numeric_boundary_cpu_draft_only','delivery_ready':False,
        'original_native_observed':False,'cases':entries}
    put(OUT/'manifest.json',manifest)
    return {'manifest_sha256':sha(OUT/'manifest.json'),'cases':len(entries)}


if __name__=='__main__':print(json.dumps(build(),sort_keys=True))

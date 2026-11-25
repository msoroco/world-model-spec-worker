"""Build a distinct paragraph (c)(2) crossing-condition request pair."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
CASE=HERE.parent
ROOT=CASE.parents[1]
SOURCE=HERE/'current-c1'/'exception_3_1'/'primary'/'construction.json'
OUT=HERE/'current-c2'
CROSSING={'exception_3_1':True,'exception_3_2':False}
DISTANCE=85.0

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def encoded(value):return json.dumps(value,indent=2,allow_nan=False)+'\n'

def build():
    base=json.loads(SOURCE.read_text());entries=[]
    for suffix,crossing in CROSSING.items():
        case_id=CASE.name+'__'+suffix
        construction=json.loads(json.dumps(base))
        construction['case_id']=case_id
        construction['status']='paragraph_c2_alternative_cpu_draft_physical_unverified'
        files={item['path']:item for item in construction['files']}
        for item in construction['files']:
            if item['path'] not in ('assignment-source.json','case-plan.json'):
                item['content']=item['content'].replace('__exception_3_1','__'+suffix)
        rows=[]
        for i in range(600):
            t=(i+1)/20;x=5+8*t
            blend=max(0,min(1,(x-17.5)/5,(20+DISTANCE+2.5-x)/5))
            y=round(-1.75-3.5*blend,6)
            rows.append({'frame':i,'time_s':t,'case_id':case_id,'candidate_id':'primary',
                'source_kind':'authored_native_request','road_id':210,'ego_x_m':round(x,6),
                'ego_y_m':y,'ego_lane_id':-2 if y < -3.5 else -1,
                'lead_x_m':round(35+4*t,6),'lead_y_m':-1.75,'lead_lane_id':-1,
                'requested_excursion_m':DISTANCE,
                'requested_private_way_or_intersection_crossing':crossing,
                'crossing_source_reviewed':False,'unmarked_pavement_verified':False,
                'one_way_designation_verified':False,'unobstructed_pavement_verified':False,
                'actual_right_pass_observed':False,'legal_verdict':None})
        files['requested-tracks.jsonl']['content']=''.join(json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in rows)
        check=files['check.py']['content']
        check=check.replace("distance = 61.06 if cfg['case_id'].endswith('exception_3_1') else 60.96",
            "distance = 85.0\n    crossing = cfg['case_id'].endswith('__exception_3_1')\n    if cfg['requested_private_way_or_intersection_crossing'] is not crossing or cfg['crossing_source_reviewed'] is not False:\n        raise ValueError('Unverified crossing request differs')")
        check=check.replace("                row['requested_excursion_m']==distance and",
            "                row['requested_excursion_m']==distance and\n                row['requested_private_way_or_intersection_crossing'] is crossing and\n                row['crossing_source_reviewed'] is False and")
        files['check.py']['content']=check
        saved=files['saved.py']['content'].replace(
            "            'unmarked_pavement_reviewed': False,\n",
            "            'unmarked_pavement_reviewed': False,\n"
            "            'private_way_or_intersection_crossing_reviewed': False,\n"
            "            'observed_private_way_or_intersection_crossing': None,\n"
            "            'paragraph_c2_verdict': None,\n")
        saved=saved.replace("        if (y0+3.5)*(y1+3.5) < 0:\n            crossings.append(x0+(x1-x0)*(-3.5-y0)/(y1-y0))",
            "        if (y0+3.5)*(y1+3.5) <= 0 and y0 != y1:\n"
            "            crossing=x0+(x1-x0)*(-3.5-y0)/(y1-y0)\n"
            "            if not crossings or abs(crossing-crossings[-1])>1e-6:\n"
            "                crossings.append(crossing)")
        files['saved.py']['content']=saved
        final=files['finalize.py']['content']
        final=final.replace('def measure_paragraph_c1(metric):','def measure_paragraph_c2(metric):')
        final=final.replace('values = measure_paragraph_c1(metric)','values = measure_paragraph_c2(metric)')
        final=final.replace("        'statutory_200ft_verdict')}",
            "        'statutory_200ft_verdict',\n"
            "        'private_way_or_intersection_crossing_reviewed',\n"
            "        'observed_private_way_or_intersection_crossing',\n"
            "        'paragraph_c2_verdict')}")
        files['finalize.py']['content']=final
        cfg=json.loads(files['config.json']['content'])
        cfg['case_id']=case_id;cfg['selected_case_id']=case_id;cfg['case']={'case_id':case_id}
        cfg['requested_excursion_m']=DISTANCE
        cfg['requested_private_way_or_intersection_crossing']=crossing
        cfg['crossing_source_reviewed']=False
        cfg['tracks_sha256']=hashlib.sha256(files['requested-tracks.jsonl']['content'].encode()).hexdigest()
        files['config.json']['content']=encoded(cfg)
        contract=json.loads(files['measurement-contract.json']['content'])
        contract['case_id']=case_id
        contract['requirements'][0]['disposition_index']=3
        contract['requirements'][0]['output_key']='paragraph_c2_crossing_source_observation'
        contract['requirements'][0]['method']='measure_paragraph_c2'
        files['measurement-contract.json']['content']=encoded(contract)
        construction['recording_description']['limitations'].append(
            'The crossing condition is an authored request. No actual intersection or private-way crossing is verified.')
        path=OUT/suffix/'primary'/'construction.json'
        put(path,construction)
        put(OUT/suffix/'measurement-contract.json',contract)
        entries.append({'case_id':case_id,'kind':'delivery','construction':suffix+'/primary/construction.json',
            'construction_sha256':sha(path),'measurement_contract':suffix+'/measurement-contract.json',
            'measurement_procedure':{'entrypoint':'finalize.py'},'candidate_risk':{'status':'physical',
            'reason':'Private-way/intersection crossing, pavement status and legal result need original source review.'},
            'candidates':[],'native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}})
    runtime=json.loads((ROOT/'batch.json').read_text())['runtime']['root']
    manifest={'format':'worker-execution-manifest','assignment_id':CASE.name,
        'runtime_manifest_sha256':sha(ROOT/runtime/'SOURCE-MANIFEST.json'),
        'status':'paragraph_c2_alternative_cpu_draft_only','delivery_ready':False,
        'original_native_observed':False,'cases':entries}
    put(OUT/'manifest.json',manifest)
    return {'manifest_sha256':sha(OUT/'manifest.json'),'cases':len(entries)}

if __name__=='__main__':print(json.dumps(build(),sort_keys=True))

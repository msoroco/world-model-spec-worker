"""Bind current exact sidewalk cases for diagnostic public CPU execution."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ASSIGNMENT=HERE.name
REPO=HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def bind():
    plan=json.loads((HERE/'case-plan.json').read_text())
    cases=[];proposal_cases=[]
    for suffix in ('probe_a','probe_b','probe_c'):
        case_id=ASSIGNMENT+'__'+suffix
        case=next(c for c in plan['cases'] if c['case_id']==case_id)
        construction=HERE/'native-draft'/suffix/'construction.json'
        inline=json.loads(construction.read_text())
        config=json.loads(next(f['content'] for f in inline['files'] if f['path']=='config.json'))
        proposal_cases.append({'case_id':case_id,
            'target_law_id':'LVMC-11-40-180-C','target_type':case['target_type'],
            'rationale':case['physical_target'],
            'variable_assignments':{'signal_request':{'kind':'controller',
                                     'value':config['signal_frame']},
                                    'pause_request':{'kind':'controller',
                                     'value':config['target_request']['pause_requested']}},
            'unresolved_judgment_calls':['actual microphone audibility at pedestrian',
                                         'legal right-of-way','covered device class'],
            'recording_description':inline['recording_description']})
        cases.append({'case_id':case_id,'kind':'delivery',
            'construction':str(construction.relative_to(HERE)),
            'construction_sha256':sha(construction),
            'measurement_contract':'measurement-'+suffix+'.json',
            'fixture_recipe':'work/'+ASSIGNMENT+'/diagnostic-recipe-'+suffix+'.json',
            'measurement_procedure':{'entrypoint':'finalize.py'},
            'candidate_risk':{'status':'physical',
                'reason':'Bicycle sidewalk motion, acoustic output/placement and pedestrian pass require original source review'},
            'candidates':[],'preparation_status':'incomplete',
            'delivery_readiness':'incomplete'})
    write(HERE/'proposals/cases.json',{
        'status':'draft','assignment_id':ASSIGNMENT,
        'law_id':'LVMC-11-40-180-C','cell_id':'C230266',
        'actor':'cycle_or_scooter_operator','sweep_specs':[],
        'cases':proposal_cases})
    write(HERE/'draft-selected-execution-manifest.json',{
        'format':'worker-execution-manifest','assignment_id':ASSIGNMENT,
        'runtime_manifest_sha256':sha(REPO/'runtime/SOURCE-MANIFEST.json'),
        'status':'partial',
        'cases':cases})
    return {'selected_case_count':len(cases),
            'manifest_sha256':sha(HERE/'draft-selected-execution-manifest.json')}


if __name__=='__main__':print(json.dumps(bind(),indent=2))

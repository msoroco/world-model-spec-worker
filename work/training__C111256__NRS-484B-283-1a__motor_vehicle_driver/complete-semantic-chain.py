"""Build and validate canonical case/binding proposals with explicit unresolved sweep."""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=HERE/'proposals'
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages
from worker_exchange.semantic_delivery import validate as validate_semantic
source=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
manifest=json.loads((HERE/'execution-manifest.json').read_text())
template=json.loads((P/'template.json').read_text())
judgment=json.loads((P/'judgment_observables_danger.json').read_text())
template['structure']['judgment_calls_needed'][0]['observable_requirements']=judgment['observable_requirements']
recording=json.loads((P/'cases.json').read_text())['cases'][0]['recording_description']
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
variables=[
 ('crosswalk_geometry','world_setup','authored two-way marked-crosswalk map; original readback pending'),
 ('device_absence_context','world_setup','no authored official devices; original actor/pixel survey pending'),
 ('cited_exception_context','world_setup','NRS 484B.287/.290/.350 applicability pending'),
 ('white_cane_declaration','world_setup','synthetic declaration only; physical cane and eligibility unverified'),
 ('ego_response_mode','controller','requested wait or overlap, measured separately'),
 ('ego_body_history','subject_behavior','original full-body vehicle trajectory'),
 ('pedestrian_body_history','subject_behavior','original full-body pedestrian trajectory')]
bindings={'cell_id':source['cell_id'],'actor':source['actor'],'status':'draft',
 'established_contexts':[{'name':'crosswalk_layout','source':'frozen catalog intersection/travel/crosswalk cell'}],
 'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}], 'context_refs':[],
 'fixed_parameters':[],
 'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,'used_by_laws':[source['law_id']]}
                       for name,kind,domain in variables]}
save(P/'bindings.json',bindings)
base={
 'crosswalk_geometry':{'kind':'world_setup','value':'authored two-way marked crosswalk y=-11 m; original map readback pending'},
 'device_absence_context':{'kind':'world_setup','value':'no authored device actors; original absence survey pending'},
 'cited_exception_context':{'kind':'world_setup','value':'NRS 484B.287/.290/.350 applicability unresolved'},
 'white_cane_declaration':{'kind':'world_setup','value':'absent'},
 'ego_response_mode':{'kind':'controller','value':'wait_for_clearance'},
 'ego_body_history':{'kind':'subject_behavior','value':None},
 'pedestrian_body_history':{'kind':'subject_behavior','value':None}}
cases=[{'case_id':HERE.name+'__baseline','target_law_id':None,'target_type':'baseline',
        'rationale':'Shared authored crosswalk setup; no baseline recording selected.',
        'variable_assignments':base,'recording_description':recording,
        'unresolved_judgment_calls':['in danger']}]
for suffix,response,cane,group,difference in [
 ('witness_1','wait_for_clearance','absent','crosswalk_pedestrian_yield','ego_response_mode'),
 ('witness_2','controlled_overlap','absent','crosswalk_pedestrian_yield','ego_response_mode'),
 ('exception_1_1','wait_for_clearance','absent','blind_white_cane_exception_applicability','white_cane_declaration'),
 ('exception_1_2','wait_for_clearance','declared_only','blind_white_cane_exception_applicability','white_cane_declaration')]:
    assignments=json.loads(json.dumps(base));assignments['ego_response_mode']['value']=response
    assignments['white_cane_declaration']['value']=cane
    cases.append({'case_id':HERE.name+'__'+suffix,'target_law_id':source['law_id'],
        'target_type':'judgment_sweep','rationale':'Conditional physical observation request; legal danger and cited exception applicability remain unresolved.',
        'paired_probe_id':group,'deliberate_differences':[difference],
        'probe':{'primary_variable':difference,'comparison_or_standard':'source-bound physical coverage; no legal label',
                 'target_value_or_branch':assignments[difference]['value']},
        'variable_assignments':assignments,'recording_description':recording,
        'unresolved_judgment_calls':['in danger']})
spec={'sweep_id':'c111256-opposite-half-danger-pending','target_law_id':source['law_id'],
      'judgment_refs':[{'phrase':'in danger','note':template['structure']['judgment_calls_needed'][0]['note']}],
      'rationale':'Opposite-half near-danger alternative needs separate physical sampling without a legal cutoff.',
      'status':'incomplete','missing_inputs':['source-grounded opposite-half pedestrian route and protected-body geometry',
        'measurable physical sampling plan and selected additional cases']}
canonical={'cell_id':source['cell_id'],'actor':source['actor'],'status':'draft',
           'cases':cases,'sweep_specs':[spec],'sweeps_expanded':True}
save(P/'canonical-cases.json',canonical)
index={'format':'worker-semantic-delivery','assignment_id':HERE.name,'stages':{
    key:{'path':'proposals/'+name+'.json','sha256':sha(P/(name+'.json'))} for key,name in
    [('relevance_batch','relevance_batch'),('relevance','relevance'),('template','template'),
     ('bindings','bindings'),('cases','canonical-cases')]}}
index['stages']['judgment_observables']=[{'path':'proposals/judgment_observables_danger.json',
    'sha256':sha(P/'judgment_observables_danger.json')}]
save(P/'semantic-index.json',index)
result=validate_semantic(HERE,source,manifest)
print(json.dumps(result))

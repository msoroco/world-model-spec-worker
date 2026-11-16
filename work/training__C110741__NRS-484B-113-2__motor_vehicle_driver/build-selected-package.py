"""Build source-bound draft canonical proposals and selected CPU manifest."""
import copy, hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
AID = ROOT.name
ASSIGNMENT = json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LID, ACTOR, CELL = ASSIGNMENT['law_id'], ASSIGNMENT['actor'], ASSIGNMENT['cell_id']
CID = {s: AID+'__selected_55c68e79__'+s for s in ('condition_a','condition_b')}
PROPOSALS = ROOT/'proposals'
PROPOSALS.mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n')

relevance = {'cell_id':CELL,'actor':ACTOR,'status':'draft','relevant_laws':[{'law_id':LID,'quote':LAW['text'],'applies_to':[ACTOR],'relevance_type':'specific_match','confidence':'medium','notes':'The frozen reverse/crosswalk cell matches the crosswalk alternative; physical map and movement remain unverified.'}],'borderline_excluded':[]}
write(PROPOSALS/'relevance_batch.json',relevance)
write(PROPOSALS/'relevance.json',relevance)
params = [
    ('crosswalk_geometry','world_setup','source surveyed crosswalk polygon and approach lane'),
    ('reverse_path_overlap','world_setup','authored reverse body path clear of versus over surveyed crosswalk'),
    ('ego_trajectory','subject_behavior','retained original frame-joined reverse pose and signed velocity'),
    ('commanded_reverse_path','controller','predeclared reverse waypoint path'),
]
template = {'template_id':LID+'@'+ACTOR,'law_id':LID,'actor':ACTOR,'status':'draft','quote':LAW['text'],'structure':{'activation':{'condition':'driver of a vehicle backing at the governed location','numeric_conditions':[]},'obligation':{'type':'must_not','description':'back into an intersection, on or over a crosswalk, or around a street corner','source_clause':'Shall not back into an intersection, on or over a crosswalk, or around a street corner.','numeric_conditions':[]},'exceptions':[],'timing':{'description':'during reverse movement over the selected physical location','numeric_conditions':[]},'judgment_calls_needed':[]},'parameter_refs':[{'name':n,'kind':k,'range_or_domain':d} for n,k,d in params]}
write(PROPOSALS/'template.json',template)
bindings={'cell_id':CELL,'actor':ACTOR,'status':'draft','established_contexts':[{'name':'reverse_crosswalk_cell','source':'frozen catalog C110741'}],'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],'context_refs':[],'fixed_parameters':[],'variable_parameters':[{'name':n,'kind':k,'range_or_domain':d,'used_by_laws':[LID]} for n,k,d in params]}
write(PROPOSALS/'bindings.json',bindings)
construction = {s:json.loads((ROOT/f'draft-candidates/{s}/primary/construction.json').read_text()) for s in CID}
desc = construction['condition_a']['recording_description']
assert all(c['recording_description']==desc for c in construction.values())
variables={
 'crosswalk_geometry':{'kind':'world_setup','value':'source surveyed crosswalk polygon and approach lane','unit':'structured'},
 'reverse_path_overlap':{'kind':'world_setup','value':'clear','unit':'categorical'},
 'ego_trajectory':{'kind':'subject_behavior','value':None,'unit':'structured'},
 'commanded_reverse_path':{'kind':'controller','value':'reverse path in C110741 lane','unit':'structured'},
}
base={'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline','rationale':'Shared reverse/crosswalk context; no accepted original is claimed.','variable_assignments':variables,'unresolved_judgment_calls':[],'recording_description':desc}
cases=[base]
for s, target, kind in [('condition_a','clear','compliant_attempt'),('condition_b','over_crosswalk','violating_attempt')]:
    vals=copy.deepcopy(variables);vals['reverse_path_overlap']['value']=target
    cases.append({'case_id':CID[s],'target_law_id':LID,'target_type':kind,'rationale':'Controlled reverse path against measured crosswalk polygon; label describes target only, actual motion unverified.','variable_assignments':vals,'unresolved_judgment_calls':[],'recording_description':desc,'paired_probe_id':'crosswalk_reverse_path','deliberate_differences':['reverse_path_overlap'],'probe':{'primary_variable':'reverse_path_overlap','comparison_or_standard':'clear versus body overlap of surveyed crosswalk','target_value_or_branch':target}})
write(PROPOSALS/'cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft','sweep_specs':[],'cases':cases})
index={'format':'worker-semantic-delivery','assignment_id':AID,'stages':{name:{'path':'proposals/'+name+'.json','sha256':sha(PROPOSALS/(name+'.json'))} for name in ('relevance_batch','relevance','template','bindings','cases')},'status':'draft','original_native_observed':False}
index['stages']['judgment_observables']=[]
write(PROPOSALS/'semantic-index.json',index)

draft=json.loads((ROOT/'draft-execution-manifest.json').read_text())
manifest={'format':'worker-execution-manifest','assignment_id':AID,'runtime_manifest_sha256':draft['runtime_manifest_sha256'],'status':'selected_cpu_partial','cases':[]}
for s,letter in [('condition_a','a'),('condition_b','b')]:
    old=next(e for e in draft['cases'] if e['case_id']==CID[s]); entry=copy.deepcopy(old)
    entry['kind']='delivery';entry.pop('id',None)
    entry['native_handoff']={'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'}
    entry['offline']={'exit_code':0,'construction_sha256':entry['construction_sha256'],'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/draft-execution-manifest.json --case {CID[s]} --candidate primary --output .runtime-work/c110741-current-offline-{letter}','log':f'current-offline-{letter}.log','log_sha256':sha(ROOT/f'current-offline-{letter}.log')}
    entry['compatibility']={'receipt':f'v2-proof-{letter}-primary.json','sha256':sha(ROOT/f'v2-proof-{letter}-primary.json'),'log':f'v2-analysis-{letter}-primary.log','negative_log':f'v2-negative-{letter}-primary.log'}
    entry['negative']={'log':f'v2-negative-{letter}-primary.log'}
    for c in entry['candidates']:
        n=c['id']; c['offline']={'exit_code':0,'construction_sha256':c['construction_sha256'],'command':f'.venv-cpu/bin/python runtime.py offline --manifest work/{AID}/draft-execution-manifest.json --case {CID[s]} --candidate {n} --output .runtime-work/c110741-current-offline-{letter}-{n}','log':f'current-offline-{letter}-{n}.log','log_sha256':sha(ROOT/f'current-offline-{letter}-{n}.log')}
        c['compatibility']={'receipt':f'v2-proof-{letter}-{n}.json','sha256':sha(ROOT/f'v2-proof-{letter}-{n}.json'),'log':f'v2-analysis-{letter}-{n}.log','negative_log':f'v2-negative-{letter}-{n}.log'}
    entry['acquisition']={name:{'entrypoint':'finalize.py','method':'derive from retained original Native sample, frame map, road geometry and synchronized source cameras','evidence':'native_samples.jsonl; video_frames.jsonl; road_geometry.json; four named source videos'} for name in ['drv.backing','st.crosswalk','st.intersection','rel.occupies','kin.heading','kin.velocity','native_body_pose_control','camera_frame_join']}
    entry['post_capture']={'recorded_only':True,'command':f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {CID[s]} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/pipeline/library --validator "$DECODER"','feedback_command':'inspect "$OUTPUT/feedback.json" on failure','test_log':f'current-v2-saved-{letter}.log','test_log_sha256':sha(ROOT/f'current-v2-saved-{letter}.log'),'test_exit_code':0}
    manifest['cases'].append(entry)
if not (ROOT/'execution-manifest.json').exists():
    write(ROOT/'execution-manifest.json',manifest)
print('authored canonical proposals and selected CPU manifest:',len(cases)-1,'cases,',sum(len(e['candidates']) for e in manifest['cases']),'fallbacks')

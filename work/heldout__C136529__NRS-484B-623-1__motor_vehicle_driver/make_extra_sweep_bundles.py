"""Build exact second speed points for the fixed safety and control sweeps."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
root=Path(__file__).resolve().parent
repo=root.parents[1]
manifest_path=root/'execution-manifest.json';manifest=json.loads(manifest_path.read_text())
plan_path=root/'case-plan.json';plan=json.loads(plan_path.read_text())
sha=lambda p:sha256(Path(p).read_bytes()).hexdigest()
def write(path,value,compact=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,separators=(',',':') if compact else None,
                               indent=None if compact else 2)+'\n')

additions=[('safety_speed_probe__slow_for_obstruction','slow_for_obstruction',6.0,
            'safety_speed_response','Fixed obstruction geometry with a higher requested ego speed.'),
           ('control_speed_probe__slow_under_control','slow_under_control',10.0,
            'control_speed_response','Fixed physical sign and route with a higher requested ego speed; governing authority unresolved.')]
for suffix,source_branch,speed,comparison_id,description in additions:
    case=root.name+'__'+suffix
    if any(e['case_id']==case for e in manifest['cases']):
        raise ValueError('Extra exact case already generated: '+case)
    source_entry=next(e for e in manifest['cases'] if e['case_id']==root.name+'__'+source_branch)
    slug=suffix.replace('__','-')
    folder=root/'cases'/slug;folder.mkdir(parents=True,exist_ok=True)
    entry=deepcopy(source_entry)
    entry['case_id']=case
    for key in ('offline','compatibility','negative','acquisition','post_capture','delivery_acceptance','physical_preparation'):
        entry.pop(key,None)
    for candidate in entry['candidates']:
        candidate.pop('offline',None);candidate.pop('compatibility',None)
    for candidate,item in [('primary',entry)]+[(c['id'],c) for c in entry['candidates']]:
        source_construction=json.loads((root/item['construction']).read_text())
        construction=deepcopy(source_construction);construction['case_id']=case
        config_file=next(f for f in construction['files'] if f['path']=='config.json')
        config=json.loads(config_file['content']);config['selected_case_id']=case
        config['case']['case_id']=case;config['ego_target_mps']=speed
        config_file['content']=json.dumps(config,indent=2)+'\n';config_file.pop('source',None)
        if candidate=='primary':
            config_path=folder/'config.json';config_path.write_text(config_file['content'])
            rel=f'cases/{slug}/construction.json'
        else:rel=f'cases/{slug}/{candidate}-construction.json'
        path=root/rel;write(path,construction)
        item['construction']=rel;item['construction_sha256']=sha(path)
    contract=json.loads((root/source_entry['measurement_contract']).read_text())
    contract['case_id']=case;contract_rel=f'cases/{slug}/measurement-contract.json';write(root/contract_rel,contract)
    entry['measurement_contract']=contract_rel
    spec=json.loads((repo/source_entry['fixture_recipe']).read_text())
    source_spec=repo/spec['sources'][0]['source'];diagnostic=json.loads(source_spec.read_text())
    diagnostic['files']['fixture-provenance.json']=json.dumps({'kind':'textual CPU diagnostic',
      'case_id':case,'physical_recording':False,'law_or_canonical_acceptance':False})+'\n'
    rows=[json.loads(line) for line in diagnostic['files']['participant_state.jsonl'].splitlines()]
    for row in rows:row['ego_speed_mps']=speed
    diagnostic['files']['participant_state.jsonl']=''.join(json.dumps(row)+'\n' for row in rows)
    diagnostic_path=folder/'diagnostic-input.json';write(diagnostic_path,diagnostic,compact=True)
    relative=str(diagnostic_path.relative_to(repo))
    recipe={'format':'worker-fixture-recipe','sources':[{'path':'diagnostic-input.json',
             'source':relative,'sha256':sha(diagnostic_path)}],
            'generator':{'source':relative,'sha256':sha(diagnostic_path)}}
    recipe_rel=f'cases/{slug}/diagnostic-recipe.json';write(root/recipe_rel,recipe)
    entry['fixture_recipe']=f'work/{root.name}/{recipe_rel}'
    manifest['cases'].append(entry)
    source_case=next(c for c in plan['cases'] if c['case_id']==root.name+'__'+source_branch)
    item=deepcopy(source_case);item['case_id']=case;item['description']=description
    item['construction_status']='primary_and_three_fallbacks_pending_exact_proofs'
    plan['cases'].append(item)
    plan['comparisons'].append({'comparison_id':comparison_id,
      'case_ids':[root.name+'__'+source_branch,case],
      'fixed_conditions':['same C136529 narrow road and route','same three vehicles',
                          'same obstruction or physical sign','same dry Native weather',
                          'same cameras and duration'],
      'deliberate_differences':['requested ego speed only; measured speed and physical response require source review']})
    print(case,entry['construction_sha256'])
write(manifest_path,manifest);write(plan_path,plan)

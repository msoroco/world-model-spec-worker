"""Reconcile the draft case proposal with the source-backed draft bindings."""
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
path = folder/'proposals/cases.json'
data = json.loads(path.read_text())
binding = json.loads((folder/'proposals/bindings.json').read_text())
template = json.loads((folder/'proposals/template.json').read_text())
law_id = template['law_id']
selected = data['cases']
assert len(selected)==2 and {case['target_type'] for case in selected}=={'judgment_sweep'}
description = selected[0]['recording_description']
for case in selected:
    assert case['recording_description']==description
    assignments = case['variable_assignments']
    assignments['commanded_approach_speed'] = {'kind':'controller','value':5.0,'unit':'m/s',
        'note':'engineering target, separate from observed ego_speed'}
    assignments['commanded_turn_path'] = {'kind':'controller','value':'left_turn_waypoint_chain',
        'unit':'authored path','note':'Native path must be confirmed from original geometry'}
    assignments['ego_speed'] = {'kind':'subject_behavior','value':None,'unit':'m/s'}
    assignments['later_opposing_braking_policy'] = {'kind':'controller',
        'value':case['case_id'].endswith('__reciprocal_yield_after_turn'),'unit':'boolean',
        'note':'exact runner policy; later opposing actor brake after subject turn onset'}
    case['deliberate_differences'] = ['later_opposing_braking_policy']
    case['probe']['primary_variable'] = 'later_opposing_braking_policy'
    case['unresolved_judgment_calls'] = [item['phrase'] for item in template['structure']['judgment_calls_needed']]

baseline = {
    'case_id':folder.name+'__baseline_context',
    'target_law_id':None,'target_type':'baseline',
    'rationale':'Shared authored junction and approach context; no separate selected recording or legal outcome.',
    'variable_assignments':json.loads(json.dumps(selected[0]['variable_assignments'])),
    'recording_description':description,
    'unresolved_judgment_calls':[],
}
data['cases'] = [baseline]+selected
data['sweep_specs'] = [
    {'sweep_id':f'c109749-{number}', 'target_law_id':law_id,
     'judgment_refs':[{'phrase':j['phrase'],'note':j['note']}],
     'status':'incomplete','rationale':'Plan physical sampling without choosing a legal cutoff.',
     'missing_inputs':['Document a feasible Native parameter range and spacing for this observable, then expand exact frozen sweep cases and prove them.']}
    for number,j in enumerate(template['structure']['judgment_calls_needed'],1)
]
names = {x['name'] for x in binding['variable_parameters']}
assert all(set(x['variable_assignments'])==names for x in data['cases'])
path.write_text(json.dumps(data,indent=2)+'\n')

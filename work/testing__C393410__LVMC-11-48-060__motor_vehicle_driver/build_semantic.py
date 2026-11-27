"""Author draft exact-law semantic stages for six C393410 route cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
P=HERE/'proposals'
LAW='LVMC-11-48-060';ACTOR='motor_vehicle_driver';TEMPLATE=LAW+'@'+ACTOR
NOTE='Authoritative route designations, complete passage, and pick-up, delivery or essential use required enroute require independent original-source review; no stop-duration proxy or worker legal verdict.'


def write(name,value):
    path=P/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return {'path':str(path.relative_to(HERE)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan=json.loads((HERE/'case-plan.json').read_text());quote=plan['law_text'];common={'status':'draft','cell_id':'C393410','actor':ACTOR}
    relevance=dict(common,relevant_laws=[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],'confidence':'low','relevance_type':'specific_match','notes':NOTE}],borderline_excluded=[])
    relevance_ref=write('relevance.json',relevance);batch_ref=write('relevance_batch.json',relevance)
    variables=(('street_class','designated truck route or non-truck connecting street'),('route_use','complete through passage or local destination'),('enroute_purpose','none, pick-up, delivery or essential use required enroute'))
    template_ref=write('template.json',{'status':'draft','law_id':LAW,'actor':ACTOR,'template_id':TEMPLATE,'quote':quote,
        'parameter_refs':[{'name':name,'kind':'world_setup','range_or_domain':domain} for name,domain in variables],
        'structure':{'activation':{'condition':'Original motor-vehicle path enters a non-truck street from one designated truck route and reaches another designated truck route.','numeric_conditions':[]},
            'obligation':{'type':'must','description':quote,'numeric_conditions':[]},
            'exceptions':[{'source_clause':clause,'description':clause+' required enroute; independent trip-purpose, premises and activity evidence needed.','numeric_conditions':[]} for clause in ('pick-up','delivery','essential use')],
            'timing':{'description':'Observe the complete original route, not an isolated stop or 45-second startup transient.','numeric_conditions':[]},
            'judgment_calls_needed':[{'phrase':'through routes','note':NOTE},{'phrase':'required enroute','note':NOTE}]}})
    judgments=[]
    for phrase in ('through routes','required enroute'):
        judgments.append(write('judgment-'+str(len(judgments)+1)+'.json',{'status':'draft','template_id':TEMPLATE,'phrase':phrase,'note':NOTE,
            'observable_requirements':{'observables':[{'name':'municipal_route_designation','unit':'source','description':'Authoritative original truck routes, non-truck connector and municipal jurisdiction.'},{'name':'ego_route_history','unit':'state','description':'Complete original vehicle path across source-identified roads.'},{'name':'enroute_context','unit':'state','description':'Original premises, activity and required trip-purpose source for all three alternatives.'}],
                'context_inputs':[{'name':'reviewed_truck_route_site','unit':'source','description':'Source-hashed municipal jurisdiction, chapter scope, street designations, controls and enroute premises.'}],
                'recording_needs':[{'name':name,'unit':unit,'description':desc} for name,unit,desc in [('municipal_route_designation','source','Original route designation and street status.'),('ego_route_history','state','Original complete source-identified route.'),('enroute_context','state','Original required enroute activity and premises.'),('governing_controls','state','Original controls and chapter context.')]],
                'sweep_dimensions':[],'landmarks':[],'limitations':['Actual Native passage, original trip-purpose and legal necessity remain under review.']}}))
    bindings_ref=write('bindings.json',dict(common,law_refs=[{'template_id':TEMPLATE,'binding_kind':'direct'}],context_refs=[],
        established_contexts=['Frozen C393410 residence-district travel cell; original route and purpose qualification pending.'],
        fixed_parameters=[{'name':'assigned_cell','value':'C393410','rationale':'Frozen catalog identity, not physical proof.'}],
        variable_parameters=[{'name':name,'kind':'world_setup','range_or_domain':domain,'used_by_laws':[LAW]} for name,domain in variables]))
    baseline=json.loads((HERE/'cases/through_no_enroute/construction.json').read_text())['recording_description']
    cases=[{'case_id':HERE.name+'__baseline','target_law_id':None,'target_type':'baseline','rationale':'Shared reviewed connecting-street and full route reference.',
        'variable_assignments':{name:{'kind':'world_setup','value':value} for name,value in [('street_class','non_truck'),('route_use','through'),('enroute_purpose','none')]},
        'recording_description':baseline,'unresolved_judgment_calls':['through routes','required enroute']}]
    for case in plan['cases']:
        short=case['case_id'].split('__')[-1];construction=json.loads((HERE/'cases'/short/'construction.json').read_text())
        values={name:case[name] for name,_ in variables}
        cases.append({'case_id':case['case_id'],'target_law_id':LAW,'target_type':'judgment_sweep',
            'rationale':'Controlled designated/non-truck route, complete/local use and each separate required-enroute exception.',
            'variable_assignments':{name:{'kind':'world_setup','value':value} for name,value in values.items()},
            'paired_probe_id':'source-gated-truck-route-passage','deliberate_differences':list(values),
            'unresolved_judgment_calls':['through routes','required enroute'],'recording_description':construction['recording_description'],
            'probe':{'primary_variable':'enroute_purpose','comparison_or_standard':'same route and full original-source context except declared comparison variable','target_value_or_branch':values}})
    sweep={'sweep_id':'source-gated-truck-route-passage','target_law_id':LAW,'judgment_refs':[{'phrase':phrase,'note':NOTE} for phrase in ('through routes','required enroute')],
        'status':'incomplete','rationale':'Original route, purpose and necessity are source judgments, not worker numeric legal cutoffs.',
        'missing_inputs':['authoritative truck route endpoints and connecting street designation','complete original route from origin through connector to destination or local endpoint','separate required-enroute pick-up, delivery and essential-use premises/activity sources']}
    write('pending-source-judgment-sweep.json',sweep)
    cases_ref=write('cases.json',dict(common,cases=cases,sweep_specs=[sweep],sweeps_expanded=True,
        sweep_expansion_scope='Six controlled source-gated original-route probes; legal judgment unresolved.'))
    index={'format':'worker-semantic-delivery','assignment_id':HERE.name,'stages':{'relevance_batch':batch_ref,'relevance':relevance_ref,'template':template_ref,'judgment_observables':judgments,'bindings':bindings_ref,'cases':cases_ref}}
    write('semantic-index.json',index)

if __name__=='__main__':build();print('six exact truck-route semantic proposals authored')

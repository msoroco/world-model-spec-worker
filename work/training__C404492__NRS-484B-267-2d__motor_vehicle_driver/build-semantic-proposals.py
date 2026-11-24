"""Build source-grounded draft semantic stages for the same-direction pair."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
A=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
LAW=A['law']
TID=LAW['id']+'@'+A['actor']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(name,value):
    path=HERE/'proposals'/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':path.relative_to(HERE).as_posix(),'sha256':sha(path)}


def parameter(kind,value,unit):
    return {'kind':kind,'value':value,'unit':unit}


def main():
    relevance={'cell_id':A['cell_id'],'actor':A['actor'],'status':'draft',
        'relevant_laws':[{'law_id':LAW['id'],'quote':LAW['text'],
            'applies_to':[A['actor']],'relevance_type':'direct','confidence':'high',
            'notes':'The selected same-direction emergency-vehicle clause governs this adjacent-lane driver response.'}],
        'borderline_excluded':[]}
    r1=put('relevance-batch.json',relevance)
    r2=put('relevance.json',relevance)
    judgments=[
        {'phrase':'authorized emergency vehicle or official vehicle of a regulatory agency making use of qualifying flashing lights',
         'note':'Verify authorization, qualifying equipment and original lamp pixels independently of a blueprint or request.'},
        {'phrase':'moving in the same direction of travel as the driver',
         'note':'Compare original actor headings, body trajectories and road lanes; the engineering heading check is not a legal cutoff.'},
        {'phrase':'not drive abreast of or overtake',
         'note':'Keep original longitudinal body overlap and order crossings distinct; no statutory numeric overlap cutoff is supplied.'},
        {'phrase':'except when otherwise directed by a law enforcement officer',
         'note':'Verify officer identity, recipient, direction content and timing from original sources.'},
        {'phrase':'preparing to move means any visible indication including movement or driver hand signals',
         'note':'The current selected moving branch does not prove a preparing-to-move alternative; retain a separate coverage gap.'}]
    parameters=[
        {'name':'requested_relative_position','kind':'controller',
         'range_or_domain':['follow_behind','drive_abreast']},
        {'name':'observed_longitudinal_overlap_m','kind':'subject_behavior',
         'range_or_domain':'original continuous body interval overlap or unknown'},
        {'name':'observed_overtake_crossings','kind':'subject_behavior',
         'range_or_domain':'original signed-order crossing count or unknown'},
        {'name':'qualified_emergency_context','kind':'world_setup',
         'range_or_domain':[True,False,None]},
        {'name':'officer_direction_context','kind':'world_setup',
         'range_or_domain':[True,False,None]}]
    template={'template_id':TID,'law_id':LAW['id'],'actor':A['actor'],
        'quote':LAW['text'],'status':'draft',
        'structure':{'law_id':LAW['id'],
            'activation':{'condition':'approaching a qualifying flashing-light emergency or regulatory vehicle moving in the same direction, unless otherwise directed by an officer',
                'numeric_conditions':[]},
            'obligation':{'description':'do not drive abreast of or overtake the qualifying vehicle in the selected same-direction movement branch',
                'type':'must_not','numeric_conditions':[]},
            'exceptions':[{'source_clause':'except when otherwise directed by a law enforcement officer',
                'description':'Original officer direction may change the response; none is inferred from a synthetic request.'}],
            'timing':{'description':'upon approach during same-direction movement; no invented spatial or temporal cutoff',
                'numeric_conditions':[]},
            'judgment_calls_needed':judgments},
        'parameter_refs':parameters}
    r3=put('template.json',template)
    observed=[]
    for i,j in enumerate(judgments):
        item={'template_id':TID,'phrase':j['phrase'],'note':j['note'],'status':'draft',
            'observable_requirements':{'observables':[
                {'name':'vehicle_poses','unit':'structured',
                 'description':'Original 20 Hz ego and emergency pose, heading, speed and complete body extents.'}],
                'context_inputs':[{'name':'emergency_context','unit':'structured',
                 'description':'Independent authority, qualifying light and officer-direction review with original sources.'}],
                'sweep_dimensions':[],'landmarks':[],
                'recording_needs':[{'name':'rel.same_direction','unit':'source_bound_structured',
                 'description':'Source-bound same-direction review joins original pose and synchronized four-camera Native frame identities.'}],
                'limitations':[j['note'],'Synthetic diagnostics do not establish physical or legal acceptance.']}}
        observed.append(put(f'judgment_observables_{i}.json',item))
    bindings={'cell_id':A['cell_id'],'actor':A['actor'],'status':'draft',
        'established_contexts':['Authored adjacent-lane same-direction two-vehicle construction; verify original Native sources'],
        'law_refs':[{'template_id':TID,'binding_kind':'direct'}],
        'context_refs':[],
        'fixed_parameters':[{'name':'qualifying_emergency_movement_context','value':'held_fixed',
            'rationale':'Both selected cases share emergency trajectory, actor identities, lanes, lighting policy and cameras; original qualification remains unverified.'}],
        'variable_parameters':[dict(item,used_by_laws=[LAW['id']]) for item in parameters]}
    r4=put('bindings.json',bindings)
    manifest=json.loads((HERE/'draft-emergency-manifest.json').read_text())
    first=json.loads((HERE/manifest['cases'][0]['construction']).read_text())
    cases=[{'case_id':HERE.name+'__baseline','target_law_id':None,
        'target_type':'baseline','rationale':'No qualifying emergency approach is asserted in the unselected neutral context.',
        'variable_assignments':{
            'requested_relative_position':parameter('controller','follow_behind','categorical'),
            'observed_longitudinal_overlap_m':parameter('subject_behavior',None,'m'),
            'observed_overtake_crossings':parameter('subject_behavior',None,'count'),
            'qualified_emergency_context':parameter('world_setup',False,'boolean'),
            'officer_direction_context':parameter('world_setup',False,'boolean')},
        'unresolved_judgment_calls':[j['phrase'] for j in judgments],
        'recording_description':first['recording_description']}]
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[-1]
        construction=json.loads((HERE/entry['construction']).read_text())
        cases.append({'case_id':entry['case_id'],'target_law_id':LAW['id'],
            'target_type':'judgment_sweep',
            'rationale':'Compare original body overlap while retaining qualification and exception judgments for independent source review.',
            'variable_assignments':{
                'requested_relative_position':parameter('controller','follow_behind' if suffix=='controlled_1' else 'drive_abreast','categorical'),
                'observed_longitudinal_overlap_m':parameter('subject_behavior',None,'m'),
                'observed_overtake_crossings':parameter('subject_behavior',None,'count'),
                'qualified_emergency_context':parameter('world_setup',None,'boolean'),
                'officer_direction_context':parameter('world_setup',None,'boolean')},
            'unresolved_judgment_calls':[j['phrase'] for j in judgments],
            'paired_probe_id':HERE.name+'__same_direction_abreast_pair',
            'deliberate_differences':['requested_relative_position'],
            'probe':{'primary_variable':'requested_relative_position',
                'comparison_or_standard':'original longitudinal body overlap and order crossings',
                'target_value_or_branch':suffix},
            'recording_description':construction['recording_description']})
    r5=put('cases.json',{'cell_id':A['cell_id'],'actor':A['actor'],
        'status':'draft','cases':cases,'sweeps_expanded':True,
        'sweep_specs':[{'sweep_id':HERE.name+'__same_direction_abreast',
            'target_law_id':LAW['id'],'status':'incomplete','judgment_refs':judgments,
            'rationale':'Two same-direction requested positions are constructed; original qualification and separate visible preparation alternatives remain unresolved.',
            'missing_inputs':['Original Native authority, lamp pixels and officer context',
                              'Separate preparing-to-move movement or hand-signal branch review']} ]})
    put('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':HERE.name,
        'stages':{'relevance_batch':r1,'relevance':r2,'template':r3,
                  'judgment_observables':observed,'bindings':r4,'cases':r5}})
    print(json.dumps({'selected_cases':len(cases)-1,'judgments':len(judgments)}))


if __name__=='__main__':main()

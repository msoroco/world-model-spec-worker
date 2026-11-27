"""Author seven canonical semantic stages for exact C135705 alley width."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
OUT=HERE/'proposals'
AID=HERE.name
LAW='NRS-484B-477-1b'
CELL='C135705'
ACTOR='motor_vehicle_driver'
TEMPLATE=LAW+'@'+ACTOR


def write(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')
    return {'path':str(path.relative_to(HERE)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def parameter(name,kind,domain):return {'name':name,'kind':kind,'range_or_domain':domain}


def build():
    original=json.loads((REPO/'inputs'/AID/'assignment.json').read_text())
    quote=original['law']['text']
    plan=json.loads((HERE/'case-plan.json').read_text())
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    description=json.loads((HERE/manifest['cases'][0]['construction']).read_text())['recording_description']
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
        'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],
            'relevance_type':'motor vehicle parking in source-qualified other alley',
            'confidence':'medium','notes':'Qualifying other alley, local ordinance and free vehicular movement require original source review.'}],
        'borderline_excluded':[]}
    batch_ref=write('relevance_batch.json',relevance)
    relevance_ref=write('relevance.json',relevance)
    judgments=[
        {'phrase':'any other alley','note':'Public highway, city block, rear access, abutting property and through-connected non-cul-de-sac status require source review.'},
        {'phrase':'free movement of vehicular traffic','note':'Continuous clear width is measured from original bodies, but realized free vehicular movement requires physical traffic review.'},
        {'phrase':'Unless otherwise provided by ordinance','note':'Local jurisdiction, ordinance text, effective period and applicability require independent source review.'}]
    refs=[parameter('available_width_ft','controller','9.9, 10.0 or 10.1 ft engineering target around statutory 10 ft'),
          parameter('other_vehicle_condition','world_setup','close or far original vehicle position'),
          parameter('ordinance_status','world_setup','none found, otherwise provides or unresolved reviewed source'),
          parameter('alley_classification','world_setup','source-qualified other alley'),
          parameter('parking_activity','controller','approach, park, hold and depart')]
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'quote':quote,
        'structure':{'law_id':LAW,
            'activation':{'condition':'A responsible person stops, stands or parks a motor vehicle in a source-qualified other alley.',
                          'numeric_conditions':[]},
            'obligation':{'description':'Do not leave less than 10 feet of the alley width available for free movement of vehicular traffic.',
                          'type':'must_not','numeric_conditions':[{'variable':'available_width_ft','operator':'<','value':10,'unit':'ft'}]},
            'exceptions':[{'source_clause':'Unless otherwise provided by ordinance of the local authority having jurisdiction',
                           'description':'Local authority ordinance otherwise provides, if source-proven and applicable.'}],
            'timing':{'description':'Measure original occupied cross-sections throughout the actual parked hold.',
                      'numeric_conditions':[]},
            'judgment_calls_needed':judgments},'parameter_refs':refs}
    template_ref=write('template.json',template)
    observed=[]
    for i,judgment in enumerate(judgments,1):
        observed.append(write('judgment-'+str(i)+'.json',{
            'template_id':TEMPLATE,'phrase':judgment['phrase'],'note':judgment['note'],
            'status':'draft','observable_requirements':{
                'observables':[{'name':'available_continuous_width_ft','unit':'ft',
                    'description':'Original continuous free cross-section width from surveyed boundaries and all body polygons.'},
                    {'name':'parking_activity','unit':'structured original source',
                     'description':'Original park and other-vehicle movement history.'}],
                'context_inputs':[{'name':'reviewed_alley_width_packet','unit':'source',
                    'description':'Original highway/alley, jurisdiction, ordinance and surveyed section provenance.'}],
                'sweep_dimensions':[],'landmarks':[],
                'recording_needs':[{'name':'four_view_frame_join','unit':'structured original source',
                    'description':'Original synchronized alley boundaries and vehicular movement views.'}],
                'limitations':['No legal meaning is inferred from a diagnostic fixture or requested parking target.']}}))
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
        'established_contexts':['Frozen C135705 narrow-road parking and other-vehicle control; actual qualifying other-alley site pending.'],
        'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
        'context_refs':[],
        'fixed_parameters':[{'name':'reviewed_alley_site','value':'source_packet_pending',
            'rationale':'Hold alley survey, vehicle dimensions, capture cadence and four views across contrasts.'}],
        'variable_parameters':[dict(ref,used_by_laws=[LAW]) for ref in refs]}
    binding_ref=write('bindings.json',binding)
    base_values={'available_width_ft':{'kind':'controller','value':10.0},
                 'other_vehicle_condition':{'kind':'world_setup','value':'far'},
                 'ordinance_status':{'kind':'world_setup','value':'reviewed unresolved'},
                 'alley_classification':{'kind':'world_setup','value':'source-qualified other alley'},
                 'parking_activity':{'kind':'controller','value':'park and hold'}}
    cases=[{'case_id':AID+'__baseline','paired_probe_id':'baseline',
        'rationale':'Shared qualified alley and motor vehicle reference; baseline is not dispatched.',
        'recording_description':description,'target_law_id':LAW,'target_type':'baseline',
        'unresolved_judgment_calls':[x['phrase'] for x in judgments],
        'variable_assignments':base_values,'deliberate_differences':[x['name'] for x in refs],
        'probe':{'primary_variable':'available_width_ft','comparison_or_standard':'original surveyed alley width',
                 'target_value_or_branch':10.0}}]
    for row in plan['cases']:
        slug=row['variant'];values={key:dict(value) for key,value in base_values.items()}
        numeric=slug.startswith('width_')
        target={'width_9_9ft':9.9,'width_10_0ft':10.,'width_10_1ft':10.1,
                'ordinance_otherwise':9.9}.get(slug,10.)
        values['available_width_ft']['value']=target
        if slug.startswith('other_vehicle'):
            values['other_vehicle_condition']['value']='close' if slug.endswith('close') else 'far'
        if slug=='ordinance_otherwise':values['ordinance_status']['value']='source-reviewed otherwise provides'
        primary='available_width_ft' if numeric else 'other_vehicle_condition' if slug.startswith('other_vehicle') else 'ordinance_status'
        probe={'primary_variable':primary,
               'comparison_or_standard':'original continuous free-width and physical traffic evidence',
               'target_value_or_branch':target if numeric else values[primary]['value']}
        if numeric:probe.update({'threshold_ref':'obligation.numeric_conditions[0]',
                                  'operator':'<','unit':'ft','test_value':target})
        case={'case_id':row['case_id'],
              'paired_probe_id':'statutory_10ft_boundary' if numeric else 'other_vehicle' if slug.startswith('other_vehicle') else 'ordinance_exception',
              'rationale':row['target_description'],'recording_description':description,
              'target_law_id':LAW,'target_type':'boundary_probe',
              'unresolved_judgment_calls':[x['phrase'] for x in judgments],
              'variable_assignments':values,'deliberate_differences':[primary],
              'probe':probe}
        if numeric:case['epsilon_used']={'value':.1,'unit':'ft',
             'rationale':'One-tenth-foot diagnostic spacing around the statutory boundary; original surveyed measurement uncertainty retained.'}
        cases.append(case)
    sweeps=[{'sweep_id':'legal_phrase_'+str(i),'target_law_id':LAW,
             'judgment_refs':[j],'status':'incomplete',
             'rationale':'No exact-law accepted judgment range or original physical outcome is supplied.',
             'missing_inputs':['Original source review for this phrase and a physical sweep range.']}
            for i,j in enumerate(judgments,1)]
    cases_ref=write('cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
                                  'cases':cases,'sweep_specs':sweeps,'sweeps_expanded':True})
    write('semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,
        'source':'Exact NRS 484B.477(1)(b) and frozen C135705 cell','status':'draft',
        'stages':{'relevance_batch':batch_ref,'relevance':relevance_ref,
                  'template':template_ref,'judgment_observables':observed,
                  'bindings':binding_ref,'cases':cases_ref}})
    return len(cases)


if __name__=='__main__':print(build())

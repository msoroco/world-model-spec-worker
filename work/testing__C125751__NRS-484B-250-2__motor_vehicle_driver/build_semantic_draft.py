"""Build source-limited canonical stage proposals for exact C125751 cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
AID=HERE.name
LAW='NRS-484B-250-2'
ACTOR='motor_vehicle_driver'
TEMPLATE=LAW+'@'+ACTOR


def write(path,object):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(object,indent=2)+'\n')


def build():
    assignment=json.loads((HERE.parents[1]/'inputs'/AID/'assignment.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    quote=assignment['law']['text']
    proposal=HERE/'proposals'
    relevance={'cell_id':'C125751','actor':ACTOR,'status':'draft',
               'relevant_laws':[{'law_id':LAW,'quote':quote,'applies_to':[ACTOR],
                                 'relevance_type':'selected crossing-entry timing rule',
                                 'confidence':'low',
                                 'notes':'Official traffic-light control is recorded in the cell; subsection 5 exclusion and subsection 4 qualification require source review.'}],
               'borderline_excluded':[]}
    write(proposal/'relevance_batch.json',relevance)
    write(proposal/'relevance.json',relevance)
    judgment={'phrase':'approximately the same time',
              'note':'The law supplies no numerical simultaneity interval.'}
    template={'template_id':TEMPLATE,'law_id':LAW,'actor':ACTOR,'quote':quote,
              'structure':{'law_id':LAW,
                           'activation':{'condition':'Two vehicles enter the same intersection from different highways at approximately the same time; ego is on the left.','numeric_conditions':[]},
                           'obligation':{'description':'Driver on left yields right-of-way to driver on right.','type':'must','numeric_conditions':[]},
                           'exceptions':[
                               {'source_clause':'Except as otherwise provided in subsection 4 [NRS-484B-250-4]',
                                'trigger':'Subsection 4 qualification','effect':'requires separate source review','replacement_obligation':'unresolved'},
                               {'source_clause':'intersections controlled by official traffic-control devices',
                                'trigger':'Official device controls intersection','effect':'subsection 5 exclusion','replacement_obligation':'unresolved'},
                               {'source_clause':'vehicles approaching each other from opposite directions, when the driver of one of the vehicles is intending to or is making a left turn',
                                'trigger':'Opposite-direction approach with intended or actual left turn','effect':'subsection 5 exclusion','replacement_obligation':'unresolved'}],
                           'timing':{'description':'Actual original crossing entry times; no legal numerical cutoff.','numeric_conditions':[]},
                           'judgment_calls_needed':[judgment]},
              'parameter_refs':[
                  {'name':'requested_entry_difference_s','kind':'controller','range_or_domain':'finite engineering target in seconds, measured separately'},
                  {'name':'requested_ego_response','kind':'controller','range_or_domain':'yield-before-entry or advance-before-other-exit request'},
                  {'name':'official_device_context','kind':'world_setup','range_or_domain':'source-reviewed control device identity and operating state'}]}
    write(proposal/'template.json',template)
    observation={'template_id':TEMPLATE,**judgment,'status':'draft',
                 'observable_requirements':{
                     'observables':[{'name':'ego_entry_bracket','unit':'structured record','description':'Original full-body crossing entry frame and time bracket.'},
                                    {'name':'other_entry_bracket','unit':'structured record','description':'Original other-vehicle crossing entry frame and time bracket.'}],
                     'context_inputs':[{'name':'crossing_geometry','unit':'structured record','description':'Source-surveyed physical intersection and distinct highway approaches.'},
                                       {'name':'governing_device','unit':'structured record','description':'Original official traffic-control device identity and state.'}],
                     'sweep_dimensions':[{'name':'requested_entry_difference_s','unit':'s','description':'Engineering crossing-entry timing request, separately verified from actual frames.'}],
                     'landmarks':[],
                     'recording_needs':[{'name':'ego_body_history','unit':'structured record','description':'Original actor footprint and Native timestamp every tick.'},
                                        {'name':'other_body_history','unit':'structured record','description':'Original other-actor footprint and Native timestamp every tick.'}],
                     'limitations':['No statutory numerical approximately-same-time cutoff is supplied.',
                                    'Official device exclusion and subsection 4 remain independent applicability questions.']}}
    write(proposal/'judgment-entry-time.json',observation)
    variables=[{'name':name,'kind':kind,'range_or_domain':domain,'used_by_laws':[LAW]}
               for name,kind,domain in (
                   ('requested_entry_difference_s','controller','engineering seconds, not a legal cutoff'),
                   ('requested_ego_response','controller','yield_before_entry or advance_before_other_exit'))]
    binding={'cell_id':'C125751','actor':ACTOR,'status':'draft',
             'established_contexts':['catalog median-opening travel cell with traffic-light control; original roadway and device applicability pending'],
             'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
             'context_refs':[],
             'fixed_parameters':[{'name':'official_device_context','value':'official_traffic_light',
                                  'rationale':'Frozen cell control; exact governing source readback remains required'}],
             'variable_parameters':variables}
    write(proposal/'bindings.json',binding)
    channel=lambda name,method:{'name':name,'unit':'structured record','sampling_rate_hz':20,
                                 'method':method,'time_window':'45 s original approach through crossing clearance',
                                 'reference_frame':'original CARLA world XY and Native elapsed time',
                                 'uncertainty':'20 Hz sampling, footprint geometry and physical visibility require review'}
    recording={'channels':[channel('ego_body_history','Post-tick original ego footprint and time'),
                           channel('other_body_history','Post-tick original other footprint and time'),
                           channel('governing_device_history','Post-tick original signal state and time'),
                           channel('original_camera_index','Four original camera frame joins')],
               'context_inputs':[{'name':'crossing_geometry','unit':'structured record','method':'SHA-sealed surveyed crossing and OpenDRIVE'},
                                 {'name':'governing_device','unit':'structured record','method':'Original governing signal actor and state'}],
               'limitations':['Physical crossing and pixel acceptance require original Native review.',
                              'Approximately-same-time and statutory applicability remain unresolved.']}
    def assignments(row):
        return {'requested_entry_difference_s':{'kind':'controller','value':row['requested_entry_difference_s'],'unit':'s',
                                                  'note':'Engineering target; actual source timing measured separately'},
                'requested_ego_response':{'kind':'controller','value':row['requested_ego_response'],
                                          'note':'Requested motion, not measured behavior'}}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
            'rationale':'Shared source-reviewed reference; no separate selected capture.',
            'variable_assignments':assignments(plan['cases'][0]),
            'recording_description':recording,'unresolved_judgment_calls':[]}]
    for row in plan['cases']:
        suffix=row['case_id'].removeprefix(AID+'__')
        variable='requested_ego_response' if suffix in ('precedence','advance') else 'requested_entry_difference_s'
        cases.append({'case_id':row['case_id'],'target_law_id':LAW,
                      'target_type':'boundary_probe','rationale':'Source-bound crossing measurement probe; no legal label.',
                      'variable_assignments':assignments(row),'recording_description':recording,
                      'unresolved_judgment_calls':[judgment['phrase']],
                      'paired_probe_id':'precedence_response' if variable=='requested_ego_response' else 'approximately_same_time_brackets',
                      'deliberate_differences':[variable],
                      'probe':{'primary_variable':variable,'comparison_or_standard':'measured original crossing',
                               'target_value_or_branch':row[variable]}})
    # A complete sweep requires a verified physical range and a frozen selected
    # grid; the three exported training probes are not a legal sweep definition.
    sweep={'sweep_id':'entry_time_source_range','target_law_id':LAW,
           'judgment_refs':[judgment], 'status':'incomplete',
           'rationale':'Qualitative phrase needs physical sampling with measured original entry times.',
           'missing_inputs':['source-verified feasible control range and spacing for this specific median opening',
                             'original device applicability and subsection 4 context review']}
    write(proposal/'cases.json',{'cell_id':'C125751','actor':ACTOR,'status':'draft',
                                 'cases':cases,'sweep_specs':[sweep]})
    paths={'relevance_batch':'relevance_batch.json','relevance':'relevance.json',
           'template':'template.json','judgment_observables':['judgment-entry-time.json'],
           'bindings':'bindings.json','cases':'cases.json'}
    stages={key:([{'path':'proposals/'+name,'sha256':hashlib.sha256((proposal/name).read_bytes()).hexdigest()} for name in value]
                 if isinstance(value,list) else {'path':'proposals/'+value,'sha256':hashlib.sha256((proposal/value).read_bytes()).hexdigest()})
            for key,value in paths.items()}
    write(proposal/'semantic-index.json',{'format':'worker-semantic-delivery','assignment_id':AID,'stages':stages})
    print('built source-limited exact canonical semantic stage chain')


if __name__=='__main__':
    build()

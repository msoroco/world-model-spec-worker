"""Canonical stage drafts for the assigned manual-wheelchair due-care branch."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
LAW_ID=ASSIGNMENT['law_id'];CELL=ASSIGNMENT['cell_id'];ACTOR=ASSIGNMENT['actor']
LAW=ASSIGNMENT['law']['text'];TEMPLATE=LAW_ID+'@'+ACTOR


def write(name,value):
    path=ROOT/'proposals'/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(ROOT)),
            'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name,description):return {'name':name,'unit':'structured record','description':description}


def main():
    refs={}
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'relevant_laws':[{'law_id':LAW_ID,'quote':LAW,'applies_to':[ACTOR],
        'relevance_type':'direct motorist-pedestrian due-care encounter',
        'confidence':'high','notes':'The frozen branch identifies a person in a manual wheelchair at the grounded pedestrian-control intersection.'}],
      'borderline_excluded':[]}
    for stage in ('relevance_batch','relevance'):
        refs[stage]=write(stage+'.json',relevance)
    judgment={'phrase':'Exercise due care','note':'The exact source supplies no numeric care or braking cutoff.'}
    parameters=[{'name':'wheelchair_path_setup','kind':'world_setup',
                 'range_or_domain':'clear path or physical crossing of ego travel corridor'},
                {'name':'ego_brake_policy','kind':'controller',
                 'range_or_domain':'engineering response to observed person/chair encounter'}]
    refs['template']=write('template.json',{'template_id':TEMPLATE,'law_id':LAW_ID,
      'actor':ACTOR,'quote':LAW,
      'structure':{'law_id':LAW_ID,
        'activation':{'condition':'Motor-vehicle driver encounters a pedestrian, including the selected person in a manual wheelchair.','numeric_conditions':[]},
        'obligation':{'description':'Exercise due care to avoid a collision with a pedestrian.','type':'must','numeric_conditions':[]},
        'exceptions':[],'timing':{'description':'Driver approach and pedestrian crossing are measured over original encounter frames.','numeric_conditions':[]},
        'judgment_calls_needed':[judgment]},'parameter_refs':parameters})
    observables=[named('ego_body_history','Original motor-vehicle body, route, speed and heading.'),
                 named('wheelchair_person_body_history','Original person body and identity as a manual-wheelchair occupant.'),
                 named('manual_wheelchair_body_history','Original chair body and asset identity.'),
                 named('ego_speed_and_brake_history','Original speed, braking and deceleration frames.'),
                 named('contact_history','Original contact events and body surface gap.')]
    contexts=[named('intersection_geometry','Original ego corridor, pedestrian crossing and map context.'),
              named('wheelchair_identity_context','Source-confirmed person and distinct manual chair association.')]
    refs['judgment_observables']=[write('judgment-1.json',{'template_id':TEMPLATE,
      'phrase':judgment['phrase'],'note':judgment['note'],'status':'draft',
      'observable_requirements':{'observables':observables,'context_inputs':contexts,
        'sweep_dimensions':[{'name':'wheelchair_path_setup','unit':'categorical',
                             'description':'Clear versus crossing physical path; no legal threshold.'}],
        'landmarks':[],'recording_needs':observables,
        'limitations':['Body separation or braking alone does not decide legal due care.',
                       'Manual-wheelchair identity and actual pixels require source review.']}})]
    refs['bindings']=write('bindings.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'established_contexts':['intersection','motor-vehicle travel','pedestrian encounter'],
      'law_refs':[{'template_id':TEMPLATE,'binding_kind':'direct'}],
      'context_refs':[],'fixed_parameters':[],
      'variable_parameters':[dict(item,used_by_laws=[LAW_ID]) for item in parameters]})
    channels=[]
    for item in observables:
        channels.append({'name':item['name'],'unit':item['unit'],'sampling_rate_hz':20,
          'method':item['description'],'time_window':'ego approach through pedestrian clearance',
          'reference_frame':'CARLA world with original frame and time',
          'uncertainty':'20 Hz sampling and simulator body precision'})
    recording={'channels':channels,'context_inputs':[{'name':item['name'],
       'unit':item['unit'],'method':item['description']} for item in contexts],
       'limitations':['Actual person/chair geometry and camera pixels require Native verification.',
                      'Legal due care remains unresolved.']}
    base={'wheelchair_path_setup':{'kind':'world_setup','value':'clear_path',
           'note':'Person in manual wheelchair stays outside ego corridor'},
          'ego_brake_policy':{'kind':'controller','value':'source_bound_engineering_response',
           'note':'Same authored controller for both cases; no legal cutoff'}}
    cases=[{'case_id':ROOT.name+'__baseline','target_law_id':None,'target_type':'baseline',
      'rationale':'Shared intersection and manual-wheelchair identity baseline.',
      'variable_assignments':base,'recording_description':recording,
      'unresolved_judgment_calls':[judgment['phrase']]}]
    for suffix,value in [('wheelchair_clear_path','clear_path'),('wheelchair_crossing','crossing')]:
        assignment=json.loads(json.dumps(base));assignment['wheelchair_path_setup']['value']=value
        cases.append({'case_id':ROOT.name+'__'+suffix,'target_law_id':LAW_ID,
          'target_type':'boundary_probe','rationale':'Paired physical path conflict comparison; due care remains a judgment.',
          'variable_assignments':assignment,'recording_description':recording,
          'unresolved_judgment_calls':[judgment['phrase']],
          'paired_probe_id':ROOT.name+'__path_pair',
          'deliberate_differences':['wheelchair_path_setup'],
          'probe':{'primary_variable':'wheelchair_path_setup',
                   'comparison_or_standard':'Original body gap, braking and contact; no legal cutoff',
                   'target_value_or_branch':value}})
    refs['cases']=write('cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'cases':cases,'sweep_specs':[{'sweep_id':'c111301-1','target_law_id':LAW_ID,
      'judgment_refs':[judgment],'status':'incomplete',
      'rationale':'Physical range and manual-wheelchair asset need original source verification.',
      'missing_inputs':['Source-backed Native manual-wheelchair geometry and crossing path',
                        'Feasible nontransient response range across encounter distances']}],
      'sweeps_expanded':True})
    write('semantic-index.json',{'format':'worker-semantic-delivery',
      'assignment_id':ROOT.name,'stages':refs})


if __name__=='__main__':main()

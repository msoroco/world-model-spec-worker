"""Source-exact canonical stage drafts for the assigned straight-arrow cell."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
LAW_ID=ASSIGNMENT['law_id'];CELL=ASSIGNMENT['cell_id'];ACTOR=ASSIGNMENT['actor']
TEMPLATE_ID=LAW_ID+'@'+ACTOR
LAW=ASSIGNMENT['law']['text']


def write(name,value):
    path=ROOT/'proposals'/name;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    return {'path':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def named(name,unit,description):return {'name':name,'unit':unit,'description':description}


def main():
    refs={}
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'relevant_laws':[{'law_id':LAW_ID,'quote':LAW,'applies_to':[ACTOR],
                        'relevance_type':'direct facing signal and straight movement','confidence':'high',
                        'notes':'The grounded cell specifies vehicular straight travel at a traffic light; sole-arrow indication remains an observed setup requirement.'}],
      'borderline_excluded':[]}
    for stage in ('relevance_batch','relevance'):refs[stage]=write(stage+'.json',relevance)
    judgments=[{'phrase':'yield the right-of-way','note':'The source supplies no numeric yielding boundary.'},
               {'phrase':'lawfully within the intersection or an adjacent crosswalk',
                'note':'Lawful presence requires independent signal and right-of-way context.'}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW_ID,'actor':ACTOR,'quote':LAW,
      'structure':{'law_id':LAW_ID,
       'activation':{'condition':'Vehicular traffic faces a green straight-through arrow alone.','numeric_conditions':[]},
       'obligation':{'description':'Straight movement is permitted; right or left turns are prohibited, and traffic must yield to lawfully present vehicles and pedestrians.','type':'must_not','numeric_conditions':[]},
       'exceptions':[],'timing':{'description':'Participant presence is evaluated at the time the signal is exhibited.','numeric_conditions':[]},
       'judgment_calls_needed':judgments},
      'parameter_refs':[{'name':'sole_arrow_setup','kind':'world_setup','range_or_domain':'verified facing signal-head indication'},
                        {'name':'participant_occupancy_setup','kind':'world_setup','range_or_domain':'lawfully present or clear physical region'},
                        {'name':'commanded_straight_path','kind':'controller','range_or_domain':'straight route through intersection'}]}
    refs['template']=write('template.json',template)
    requirements=[
      {'observables':[named('ego_body_history','structured record','Original ego body, heading and entry timing.'),
                      named('vehicle_body_history','structured record','Original other-vehicle bodies and motion.'),
                      named('pedestrian_body_history','structured record','Original pedestrian bodies and motion.'),
                      named('signal_head_history','structured record','Original facing head illuminated indications and exhibition frames.')],
       'context_inputs':[named('intersection_geometry','structured record','Original intersection extent and stop line.'),
                         named('crosswalk_geometry','structured record','Original adjacent crosswalk extents.'),
                         named('lawful_presence_context','structured record','Independent lawful-presence source for each participant.')],
       'sweep_dimensions':[named('participant_occupancy_setup','categorical','Physical occupancy setup varied without choosing a legal yield cutoff.')],
       'landmarks':[],
       'recording_needs':[named('ego_body_history','structured record','Original ego body, heading and entry timing.'),
                          named('vehicle_body_history','structured record','Original other-vehicle bodies and motion.'),
                          named('pedestrian_body_history','structured record','Original pedestrian bodies and motion.'),
                          named('signal_head_history','structured record','Original facing head indication and exhibition frames.')],
       'limitations':['A generic green lamp does not prove a sole straight arrow.',
                      'Body overlap alone does not establish lawful presence or legal yielding.']}
      for _ in judgments]
    refs['judgment_observables']=[write('judgment-'+str(i)+'.json',
         {'template_id':TEMPLATE_ID,'phrase':judgment['phrase'],'note':judgment['note'],
          'status':'draft','observable_requirements':requirement})
         for i,(judgment,requirement) in enumerate(zip(judgments,requirements),1)]
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'established_contexts':['intersection','straight movement','traffic light'],
      'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}], 'context_refs':[],
      'fixed_parameters':[],
      'variable_parameters':[{'name':'sole_arrow_setup','kind':'world_setup',
                               'range_or_domain':'source-verified sole straight arrow','used_by_laws':[LAW_ID]},
                             {'name':'participant_occupancy_setup','kind':'world_setup',
                              'range_or_domain':'lawfully present participant occupancy at signal exhibition','used_by_laws':[LAW_ID]},
                             {'name':'commanded_straight_path','kind':'controller',
                              'range_or_domain':'straight path, no turn command','used_by_laws':[LAW_ID]}]}
    refs['bindings']=write('bindings.json',binding)
    channels=[]
    for name,method in [('signal_head_history','Per-frame facing-head indication readback'),
                        ('ego_body_history','Per-frame Native ego body and heading'),
                        ('vehicle_body_history','Per-frame Native other-vehicle body readback'),
                        ('pedestrian_body_history','Per-frame Native pedestrian body readback')]:
        channels.append({'name':name,'unit':'structured record','sampling_rate_hz':20,
                         'method':method,'time_window':'signal exhibition through intersection clearance',
                         'reference_frame':'CARLA world with frame and time','uncertainty':'20 Hz sampling and simulator geometry precision'})
    contexts=[{'name':name,'unit':'structured record','method':method}
              for name,method in [('intersection_geometry','Native map and stop-line readback'),
                                  ('crosswalk_geometry','Native map crosswalk readback'),
                                  ('lawful_presence_context','Independent phase and priority source review')]]
    recording={'channels':channels,'context_inputs':contexts,
               'limitations':['Arrow asset and lawful presence need source verification.',
                              'Physical occupancy is retained without a legal yield verdict.']}
    base={'sole_arrow_setup':{'kind':'world_setup','value':'source_verified_sole_straight_arrow',
                              'note':'Target setup only; actual Native aspect must be read back'},
          'participant_occupancy_setup':{'kind':'world_setup','value':'clear','note':'Target occupancy'},
          'commanded_straight_path':{'kind':'controller','value':'straight','note':'Same straight route in both probes'}}
    cases=[{'case_id':ROOT.name+'__baseline','target_law_id':None,'target_type':'baseline',
            'rationale':'Shared straight-arrow physical baseline; judgment unresolved.',
            'variable_assignments':base,'recording_description':recording,
            'unresolved_judgment_calls':[j['phrase'] for j in judgments]}]
    for suffix,occupancy in [('clear_straight','clear'),('yield_straight','lawfully_present')]:
        import copy
        assignments=copy.deepcopy(base);assignments['participant_occupancy_setup']['value']=occupancy
        cases.append({'case_id':ROOT.name+'__'+suffix,'target_law_id':LAW_ID,'target_type':'boundary_probe',
                      'rationale':'Paired physical occupancy comparison under the same sole straight arrow.',
                      'variable_assignments':assignments,'recording_description':recording,
                      'unresolved_judgment_calls':[j['phrase'] for j in judgments],
                      'paired_probe_id':ROOT.name+'__occupancy_pair',
                      'deliberate_differences':['participant_occupancy_setup'],
                      'probe':{'primary_variable':'participant_occupancy_setup',
                               'comparison_or_standard':'Original lawful-presence and yielding evidence; no legal cutoff assumed',
                               'target_value_or_branch':occupancy}})
    sweeps=[{'sweep_id':'c111125-'+str(i),'target_law_id':LAW_ID,
             'judgment_refs':[j],'status':'incomplete',
             'rationale':'Physical sweep range and lawful-presence source need construction and source verification.',
             'missing_inputs':['Source-verified sole-arrow Native head and lawful-presence context',
                               'Feasible physical occupancy and response sweep range']}
            for i,j in enumerate(judgments,1)]
    refs['cases']=write('cases.json',{'cell_id':CELL,'actor':ACTOR,'status':'draft',
                                    'cases':cases,'sweep_specs':sweeps,'sweeps_expanded':True})
    write('semantic-index.json',{'format':'worker-semantic-delivery',
                                 'assignment_id':ROOT.name,'stages':refs})


if __name__=='__main__':main()

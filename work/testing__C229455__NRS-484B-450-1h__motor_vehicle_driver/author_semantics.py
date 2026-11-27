"""Draft canonical semantic stages for exact NRS 484B.450(1)(h)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
from safety_zone import CASES, THIRTY_FT_M
from author_bundles import recording
ROOT=Path(__file__).resolve().parent
AID=ROOT.name;LAW='NRS-484B-450-1h';CELL='C229455';ACTOR='motor_vehicle_driver'
TEXT=('A person shall not stop, stand or park a vehicle, except when necessary to avoid '
      'conflict with other traffic or in compliance with law or the directions of a police '
      'officer or official traffic-control device, in any of the following places: '
      'Between a safety zone and the adjacent curb or within 30 feet of points on the curb '
      'immediately opposite the ends of a safety zone.')
PARAMETERS=(('placement','world_setup','between zone and adjacent curb, outside corridor, or opposite end band'),
 ('selected_end','world_setup','west or east end of official safety zone'),
 ('signed_end_station_m','subject_behavior','measured original body centre station from curb point opposite selected end'),
 ('halt_activity','world_setup','stop, stand or park'),
 ('exception_context','world_setup','none, traffic conflict, law, officer or official device'))
JUDGMENTS=(('necessary to avoid conflict with other traffic',
             ('traffic_motion_history','halt_activity_history','exception_context')),
           ('safety zone',('official_zone_designation','zone_boundaries','adjacent_curb')))

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def observable(phrase,names):
    items=[{'name':name,'unit':'structured original record',
      'description':'Original source-bound '+name.replace('_',' ')} for name in names]
    return {'template_id':LAW+'@'+ACTOR,'phrase':phrase,'note':'',
      'observable_requirements':{'observables':items,'context_inputs':[],
       'sweep_dimensions':[],'landmarks':[],'recording_needs':items,
       'limitations':['Official designation and exception applicability need original independent review.',
                      'No physical measurement alone resolves a legal judgment.']}}

def main():
    folder=ROOT/'proposals'
    relevance={'cell_id':CELL,'actor':ACTOR,'status':'draft','relevant_laws':[{
      'law_id':LAW,'quote':TEXT,'applies_to':[ACTOR],'relevance_type':'specific_match',
      'confidence':'high','notes':'Fixed safety-zone parking task; official designation and actual placement still require original review.'}],
      'borderline_excluded':[]}
    write(folder/'relevance.json',relevance);write(folder/'relevance_batch.json',relevance)
    exceptions=[{'trigger':phrase,'effect':'exception to prohibition',
      'replacement_obligation':None,'source_clause':phrase} for phrase in (
      'necessary to avoid conflict with other traffic','in compliance with law',
      'the directions of a police officer','official traffic-control device')]
    template={'template_id':LAW+'@'+ACTOR,'law_id':LAW,'actor':ACTOR,'quote':TEXT,
      'structure':{'law_id':LAW,
        'activation':{'condition':'Vehicle on a highway with a source-established safety zone and adjacent curb.',
                      'numeric_conditions':[]},
        'obligation':{'description':TEXT,'type':'must_not',
          'numeric_conditions':[{'variable':'signed_end_station_m','operator':'<=',
                                 'value':30,'unit':'ft',
                                 'source_clause':'within 30 feet of points on the curb immediately opposite the ends of a safety zone'}]},
        'exceptions':exceptions,
        'timing':{'description':'Observe approach, terminal halt, original body and curb reference, traffic and authority context.',
                  'numeric_conditions':[]},
        'judgment_calls_needed':[{'phrase':phrase,'note':''} for phrase,_ in JUDGMENTS]},
      'parameter_refs':[{'name':name,'kind':kind,'range_or_domain':domain}
                        for name,kind,domain in PARAMETERS]}
    write(folder/'template.json',template)
    for i,(phrase,names) in enumerate(JUDGMENTS):write(folder/('judgment-'+str(i)+'.json'),observable(phrase,names))
    binding={'cell_id':CELL,'actor':ACTOR,'status':'draft',
      'established_contexts':['road','park maneuver','safety_zone'],
      'law_refs':[{'template_id':LAW+'@'+ACTOR,'binding_kind':'direct'}],
      'context_refs':[],'fixed_parameters':[],
      'variable_parameters':[{'name':name,'kind':kind,'range_or_domain':domain,
         'used_by_laws':[LAW]} for name,kind,domain in PARAMETERS]}
    write(folder/'bindings.json',binding)
    description=recording()
    cases={'cell_id':CELL,'actor':ACTOR,'status':'draft','sweeps_expanded':True,'cases':[],
      'sweep_specs':[{'sweep_id':'zone_end_distance_and_conflict_context',
        'target_law_id':LAW,'status':'incomplete',
        'judgment_refs':[{'phrase':phrase,'note':''} for phrase,_ in JUDGMENTS],
        'rationale':'Controlled original-source placement, 30-foot boundary and exception probes; no legal judgment cutoff selected.',
        'missing_inputs':['Original independent source establishes designation, visibility and conflict necessity; no finite range for qualitative phrase.']}]}
    base={'placement':{'kind':'world_setup','value':'between'},
          'selected_end':{'kind':'world_setup','value':'west'},
          'signed_end_station_m':{'kind':'subject_behavior','value':None},
          'halt_activity':{'kind':'world_setup','value':'park'},
          'exception_context':{'kind':'world_setup','value':'none'}}
    cases['cases'].append({'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
      'rationale':'Unselected reference definition; no extra GPU job.',
      'variable_assignments':base,'unresolved_judgment_calls':[],
      'recording_description':description})
    for c in CASES:
        distance_probe = c.case_id in ('west_end_below_30ft', 'west_end_at_30ft',
                                       'west_end_above_30ft')
        distance_ft = c.offset_m / 0.3048 if distance_probe else None
        variables={'placement':{'kind':'world_setup','value':c.placement},
          'selected_end':{'kind':'world_setup','value':c.end},
          'signed_end_station_m':{'kind':'subject_behavior','value':None},
          'halt_activity':{'kind':'world_setup','value':c.activity},
          'exception_context':{'kind':'world_setup','value':c.exception}}
        cases['cases'].append({'case_id':AID+'__'+c.case_id,'target_law_id':LAW,
          'target_type':'boundary_probe',
          'rationale':'Original-source safety-zone corridor, both ends, statutory 30-foot distance and exceptions; legal outcome unresolved.',
          'variable_assignments':variables,
          'unresolved_judgment_calls':[phrase for phrase,_ in JUDGMENTS]+['official designation','exception applicability'],
          'recording_description':description,
          'paired_probe_id':'safety_zone_corridor_end_station_and_exceptions',
          'deliberate_differences':list(variables),
          'probe':{'primary_variable':'signed_end_station_m' if distance_probe else 'placement',
            'comparison_or_standard':'original source-bound controlled contrast and statutory 30-foot reference',
            'target_value_or_branch':{'placement':c.placement,'end':c.end,
                                     'engineering_offset_m':c.offset_m,
                                     'statutory_reference_m':THIRTY_FT_M},
            **({'threshold_ref':'obligation.numeric_conditions[0]',
                'operator':'<=','unit':'ft','test_value':distance_ft}
               if distance_probe else {})},
          **({'epsilon_used':{'value':0.1/0.3048,'unit':'ft',
               'rationale':'Engineering station spacing of 0.1 m around the exact 30-foot statutory boundary.'}}
             if distance_probe else {})})
    write(folder/'cases.json',cases)
    refs={stage:{'path':'proposals/'+stage+'.json',
      'sha256':hashlib.sha256((folder/(stage+'.json')).read_bytes()).hexdigest()}
      for stage in ('relevance_batch','relevance','template','bindings','cases')}
    refs['judgment_observables']=[{'path':'proposals/judgment-'+str(i)+'.json',
      'sha256':hashlib.sha256((folder/('judgment-'+str(i)+'.json')).read_bytes()).hexdigest()}
      for i in range(len(JUDGMENTS))]
    write(folder/'semantic-index.json',{'format':'worker-semantic-delivery',
      'assignment_id':AID,'stages':refs})
if __name__=='__main__':main()

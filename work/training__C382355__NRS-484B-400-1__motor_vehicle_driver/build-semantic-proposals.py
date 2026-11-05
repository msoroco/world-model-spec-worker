"""Build source-grounded, unselected semantic stage drafts for C382355 right-turn lane."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
ASSIGNMENT=json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
LAW=ASSIGNMENT['law_record']
AID=FOLDER.name
TEMPLATE_ID=LAW['id']+'@'+ASSIGNMENT['actor']


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(content,indent=2)+'\n')
    return {'path':str(path.relative_to(FOLDER)),'sha256':sha(path)}


def assignment(kind,value,unit):return {'kind':kind,'value':value,'unit':unit}


def main():
    proposal_dir=FOLDER/'proposals'
    relevance={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
       'relevant_laws':[{'law_id':LAW['id'],'quote':LAW['text'],
        'applies_to':[ASSIGNMENT['actor']],'relevance_type':'direct',
        'confidence':'high','notes':'Exact clause covers the frozen right-turn-lane intersection and the approach and turn.'}],
       'borderline_excluded':[]}
    r1=write(proposal_dir/'relevance-batch.json',relevance)
    r2=write(proposal_dir/'relevance.json',relevance)
    parameters=[
      {'name':'commanded_approach_lane_y_m','kind':'controller','range_or_domain':'rightmost and inner approach lane centers, measured separately'},
      {'name':'commanded_turn_path','kind':'controller','range_or_domain':['right_turn','through']},
      {'name':'actual_right_turn_lane_occupancy','kind':'subject_behavior','range_or_domain':'measured Native full-body approach lane occupancy, initially unknown'},
      {'name':'actual_turn_completion','kind':'subject_behavior','range_or_domain':[True,False,None]}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],
      'quote':LAW['text'],'status':'draft',
      'structure':{'law_id':LAW['id'],
       'activation':{'condition':'driver intends a right turn at an intersection',
                     'numeric_conditions':[]},
       'obligation':{'description':'make both the right-turn approach and turn from the right-turn lane when present, otherwise from the extreme right lane',
                     'type':'must','numeric_conditions':[]},
       'exceptions':[],
       'timing':{'description':'during the approach and right turn','numeric_conditions':[]},
       'judgment_calls_needed':[{'phrase':'intends to turn',
          'note':'Interior intent is not directly observable; preserve authored command and observed turn separately.'}]},
      'parameter_refs':parameters}
    r3=write(proposal_dir/'template.json',template)
    judgment={'template_id':TEMPLATE_ID,'phrase':'intends to turn',
      'note':'Interior intent is not directly observable; preserve authored command and observed turn separately.',
      'status':'draft','observable_requirements':{
        'observables':[{'name':'native_body_pose_control','unit':'structured',
           'description':'Original pose and heading change through the intersection'}],
        'context_inputs':[{'name':'surveyed_right_turn_lane_intersection','unit':'structured',
           'description':'Original map/lane context for the intersection'}],
        'sweep_dimensions':[],'landmarks':[],
        'recording_needs':[{'name':'drv.turning','unit':'structured',
           'description':'Authored turn request retained separately from observed motion'}],
        'limitations':['Original motion cannot establish a private mental state or legal intent by itself.']}}
    rj=write(proposal_dir/'judgment-intends-to-turn.json',judgment)
    bindings={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
      'established_contexts':['authored right-turn-lane intersection; verify actual Native lane marking and design before use'],
      'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}],
      'context_refs':[],
      'fixed_parameters':[{'name':'right_turn_lane_intersection','value':True,
        'rationale':'Frozen cell and exact clause; actual right-only lane design needs Native map and saved-pixel confirmation'}],
      'variable_parameters':[dict(item,used_by_laws=[LAW['id']]) for item in parameters]}
    r4=write(proposal_dir/'bindings.json',bindings)
    construction=json.loads((FOLDER/'draft-candidates/witness_1/primary/construction.json').read_text())
    recording=construction['recording_description']
    def values(approach_y,turn):
        return {'commanded_approach_lane_y_m':assignment('controller',approach_y,'m'),
                'commanded_turn_path':assignment('controller',turn,'categorical'),
                'actual_right_turn_lane_occupancy':assignment('subject_behavior',None,'boolean'),
                'actual_turn_completion':assignment('subject_behavior',None,'boolean')}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
       'rationale':'Activation absent because the controller requests straight travel; neutral context only, unselected.',
       'variable_assignments':values(-5.25,'through'),'unresolved_judgment_calls':[],
       'recording_description':recording}]
    for suffix,approach_y,target_type in (('witness_1',-5.25,'boundary_probe'),
                                        ('witness_2',-1.75,'boundary_probe')):
        cases.append({'case_id':AID+'__'+suffix,'target_law_id':LAW['id'],
           'target_type':target_type,
           'rationale':'Compare requested rightmost versus inner approach lanes while keeping the same right turn; outcome awaits measured Native evidence and independent review.',
           'variable_assignments':values(approach_y,'right_turn'),
           'unresolved_judgment_calls':['intends to turn'],
           'paired_probe_id':AID+'__right_lane_pair',
           'deliberate_differences':['commanded_approach_lane_y_m'],
           'probe':{'primary_variable':'commanded_approach_lane_y_m',
                    'comparison_or_standard':'right-turn lane versus inner approach lane',
                    'target_value_or_branch':approach_y},
           'recording_description':recording})
    case_proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],
                   'status':'draft','cases':cases,'sweep_specs':[
        {'sweep_id':'c382355-intent-coverage-pending','target_law_id':LAW['id'],
         'judgment_refs':[{'phrase':'intends to turn','note':judgment['note']}],
         'rationale':'Additional coverage of the unresolved intent judgment requires measured Native feasibility.',
         'status':'incomplete',
         'missing_inputs':['Native right-only lane design confirmation and an independent judgment coverage design']} ]}
    r5=write(proposal_dir/'cases.json',case_proposal)
    index={'format':'worker-semantic-delivery-v1','assignment_id':AID,
           'status':'draft_not_delivery_selected',
           'stages':{'relevance_batch':r1,'relevance':r2,'template':r3,
                     'judgment_observables':[rj],'bindings':r4,'cases':r5}}
    write(proposal_dir/'semantic-index.json',index)
    print(json.dumps({'semantic_stages':6,'selected_case_drafts':2,
                      'baseline_unselected':1,'judgment_phrases':1,
                      'judgment_sweep':'incomplete'}))


if __name__=='__main__':main()

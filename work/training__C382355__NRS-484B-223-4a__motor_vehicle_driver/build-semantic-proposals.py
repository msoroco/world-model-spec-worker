"""Build source-grounded, unselected NRS 484B.223(4)(a) semantic drafts."""
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
        'confidence':'high','notes':'Exact clause concerns right-only-lane use and subsequent right turn; actual lane design and straight-probe cell fit require review.'}],
       'borderline_excluded':[]}
    r1=write(proposal_dir/'relevance-batch.json',relevance)
    r2=write(proposal_dir/'relevance.json',relevance)
    parameters=[
      {'name':'commanded_subsequent_movement','kind':'controller','range_or_domain':['right_turn','straight_through']},
      {'name':'actual_right_only_lane_occupancy','kind':'subject_behavior','range_or_domain':'measured original Native body and lane IDs, initially unknown'},
      {'name':'observed_subsequent_movement','kind':'subject_behavior','range_or_domain':['right_turn_follows','straight_follows',None]}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],
      'quote':LAW['text'],'status':'draft',
      'structure':{'law_id':LAW['id'],
       'activation':{'condition':'highway has a single right lane designed only for turning and the vehicle is driven in it',
                     'numeric_conditions':[]},
       'obligation':{'description':'drive in that right turn lane only for the purpose of making a right turn',
                     'type':'must','numeric_conditions':[]},
       'exceptions':[],
       'timing':{'description':'right-only lane occupancy precedes the observed subsequent movement','numeric_conditions':[]},
       'judgment_calls_needed':[{'phrase':'for the purpose of making a right turn',
          'note':'Private purpose is not directly observable; preserve authored command and observed subsequent movement separately.'}]},
      'parameter_refs':parameters}
    r3=write(proposal_dir/'template.json',template)
    judgment={'template_id':TEMPLATE_ID,'phrase':'for the purpose of making a right turn',
      'note':'Private purpose is not directly observable; preserve authored command and observed subsequent movement separately.',
      'status':'draft','observable_requirements':{
        'observables':[{'name':'native_body_pose_control','unit':'structured',
           'description':'Original right-only lane body occupancy, road/lane IDs and subsequent heading and exit'}],
        'context_inputs':[{'name':'surveyed_right_turn_lane_intersection','unit':'structured',
           'description':'Original Native map/lane and right-only designation context'}],
        'sweep_dimensions':[],'landmarks':[],
        'recording_needs':[{'name':'drv.turning','unit':'structured',
           'description':'Authored movement request retained separately from observed motion'}],
        'limitations':['Original motion cannot establish private purpose by itself; subsequent turn is an observable proxy only.']}}
    rj=write(proposal_dir/'judgment-purpose.json',judgment)
    bindings={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
      'established_contexts':['authored right-only-lane intersection; verify actual Native lane designation and straight connector before use'],
      'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}],
      'context_refs':[],
      'fixed_parameters':[{'name':'right_only_lane_intersection_authored','value':True,
        'rationale':'Authored map proposal only; actual right-only lane design needs Native map and saved-pixel confirmation'}],
      'variable_parameters':[dict(item,used_by_laws=[LAW['id']]) for item in parameters]}
    r4=write(proposal_dir/'bindings.json',bindings)
    construction=json.loads((FOLDER/'draft-candidates/controlled_1/primary/construction.json').read_text())
    recording=construction['recording_description']
    def values(movement):
        return {'commanded_subsequent_movement':assignment('controller',movement,'categorical'),
                'actual_right_only_lane_occupancy':assignment('subject_behavior',None,'boolean'),
                'observed_subsequent_movement':assignment('subject_behavior',None,'categorical')}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
       'rationale':'Activation absent because the subject does not enter the right-only lane; neutral context only, unselected.',
       'variable_assignments':values('right_turn'),'unresolved_judgment_calls':[],
       'recording_description':recording}]
    for suffix,movement,target_type in (('controlled_1','right_turn','boundary_probe'),
                                        ('controlled_2','straight_through','boundary_probe')):
        cases.append({'case_id':AID+'__'+suffix,'target_law_id':LAW['id'],
           'target_type':target_type,
           'rationale':'Compare subsequent right turn versus straight continuation after the same right-only lane approach; purpose and legal outcome await independent review.',
           'variable_assignments':values(movement),
           'unresolved_judgment_calls':['for the purpose of making a right turn'],
           'paired_probe_id':AID+'__subsequent_movement_pair',
           'deliberate_differences':['commanded_subsequent_movement'],
           'probe':{'primary_variable':'commanded_subsequent_movement',
                    'comparison_or_standard':'right turn versus straight continuation after right-only lane occupancy',
                    'target_value_or_branch':movement},
           'recording_description':recording})
    case_proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],
                   'status':'draft','cases':cases,'sweep_specs':[
        {'sweep_id':'c382355-4a-purpose-coverage-pending','target_law_id':LAW['id'],
         'judgment_refs':[{'phrase':'for the purpose of making a right turn','note':judgment['note']}],
         'rationale':'Additional coverage of private purpose requires measured Native feasibility and independent judgment design.',
         'status':'incomplete',
         'missing_inputs':['Native right-only lane design confirmation','straight-probe fit with frozen right-turn maneuver','independent purpose judgment coverage design']} ]}
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

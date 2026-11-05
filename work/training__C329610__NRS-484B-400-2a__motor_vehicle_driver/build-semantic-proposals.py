"""Build source-grounded, unselected semantic stage drafts for C329610 2a."""
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
        'confidence':'high','notes':'Exact clause directly covers the frozen two-way intersection and left-turn approach.'}],
       'borderline_excluded':[]}
    r1=write(proposal_dir/'relevance-batch.json',relevance)
    r2=write(proposal_dir/'relevance.json',relevance)
    parameters=[
      {'name':'commanded_approach_lateral_m','kind':'controller','range_or_domain':'right-half lane centers, measured separately'},
      {'name':'commanded_turn_path','kind':'controller','range_or_domain':['left_turn','through']},
      {'name':'actual_approach_lateral_m','kind':'subject_behavior','range_or_domain':'measured Native lateral offset, initially unknown'},
      {'name':'actual_turn_completion','kind':'subject_behavior','range_or_domain':[True,False,None]}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],
      'quote':LAW['text'],'status':'draft',
      'structure':{'law_id':LAW['id'],
       'activation':{'condition':'driver intends a left turn at an intersection of two two-directional highways',
                     'numeric_conditions':[]},
       'obligation':{'description':'approach in the portion of the right half nearest the centerline of the approached highway',
                     'type':'must','numeric_conditions':[]},
       'exceptions':[],
       'timing':{'description':'approach before first intersection entry','numeric_conditions':[]},
       'judgment_calls_needed':[]},
      'parameter_refs':parameters}
    r3=write(proposal_dir/'template.json',template)
    bindings={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft',
      'established_contexts':['authored two-way-to-two-way intersection; verify actual Native directions before use'],
      'law_refs':[{'template_id':TEMPLATE_ID,'binding_kind':'direct'}],
      'context_refs':[],
      'fixed_parameters':[{'name':'two_way_intersection','value':True,
        'rationale':'Frozen cell and exact clause; actual Native lane directions require measured confirmation'}],
      'variable_parameters':[dict(item,used_by_laws=[LAW['id']]) for item in parameters]}
    r4=write(proposal_dir/'bindings.json',bindings)
    construction=json.loads((FOLDER/'draft-candidates/controlled_1/primary/construction.json').read_text())
    recording=construction['recording_description']
    def values(lateral,turn):
        return {'commanded_approach_lateral_m':assignment('controller',lateral,'m'),
                'commanded_turn_path':assignment('controller',turn,'categorical'),
                'actual_approach_lateral_m':assignment('subject_behavior',None,'m'),
                'actual_turn_completion':assignment('subject_behavior',None,'boolean')}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
       'rationale':'Activation absent because the controller requests straight travel; neutral context only, unselected.',
       'variable_assignments':values(1.75,'through'),'unresolved_judgment_calls':[],
       'recording_description':recording}]
    for suffix,lateral,target_type in (('controlled_1',1.75,'compliant_attempt'),
                                        ('controlled_2',5.25,'violating_attempt')):
        cases.append({'case_id':AID+'__'+suffix,'target_law_id':LAW['id'],
           'target_type':target_type,
           'rationale':'Compare requested inner versus outer approach placement in the same right half; outcome awaits measured Native evidence and independent review.',
           'variable_assignments':values(lateral,'left_turn'),
           'unresolved_judgment_calls':[],
           'paired_probe_id':AID+'__approach_pair',
           'deliberate_differences':['commanded_approach_lateral_m'],
           'probe':{'primary_variable':'commanded_approach_lateral_m',
                    'comparison_or_standard':'inner versus outer approach position within the right half',
                    'target_value_or_branch':lateral},
           'recording_description':recording})
    case_proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],
                   'status':'draft','cases':cases,'sweep_specs':[]}
    r5=write(proposal_dir/'cases.json',case_proposal)
    index={'format':'worker-semantic-delivery-v1','assignment_id':AID,
           'status':'draft_not_delivery_selected',
           'stages':{'relevance_batch':r1,'relevance':r2,'template':r3,
                     'judgment_observables':[],'bindings':r4,'cases':r5}}
    write(proposal_dir/'semantic-index.json',index)
    print(json.dumps({'semantic_stages':5,'selected_case_drafts':2,
                      'baseline_unselected':1,'judgment_phrases':0}))


if __name__=='__main__':main()

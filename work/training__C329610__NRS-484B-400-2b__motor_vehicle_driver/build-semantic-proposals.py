"""Build source-grounded, unselected semantic stage drafts for C329610 2b."""
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
        'confidence':'high','notes':'Exact clause directly covers the frozen two-way intersection and left-turn destination exit.'}],
       'borderline_excluded':[]}
    r1=write(proposal_dir/'relevance-batch.json',relevance)
    r2=write(proposal_dir/'relevance.json',relevance)
    parameters=[
      {'name':'commanded_destination_exit_x_m','kind':'controller','range_or_domain':'two destination exit-side path centers, measured separately'},
      {'name':'commanded_turn_path','kind':'controller','range_or_domain':['left_turn','through']},
      {'name':'actual_destination_exit_side','kind':'subject_behavior','range_or_domain':'measured Native full-body exit side, initially unknown'},
      {'name':'actual_turn_completion','kind':'subject_behavior','range_or_domain':[True,False,None]}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],
      'quote':LAW['text'],'status':'draft',
      'structure':{'law_id':LAW['id'],
       'activation':{'condition':'driver intends a left turn at an intersection of two two-directional highways',
                     'numeric_conditions':[]},
       'obligation':{'description':'leave the intersection right of the centerline of the highway entered',
                     'type':'must','numeric_conditions':[]},
       'exceptions':[],
       'timing':{'description':'after entry, at first full-body destination exit','numeric_conditions':[]},
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
    construction=json.loads((FOLDER/'draft-candidates/witness_1/primary/construction.json').read_text())
    recording=construction['recording_description']
    def values(exit_x,turn):
        return {'commanded_destination_exit_x_m':assignment('controller',exit_x,'m'),
                'commanded_turn_path':assignment('controller',turn,'categorical'),
                'actual_destination_exit_side':assignment('subject_behavior',None,'categorical'),
                'actual_turn_completion':assignment('subject_behavior',None,'boolean')}
    cases=[{'case_id':AID+'__baseline','target_law_id':None,'target_type':'baseline',
       'rationale':'Activation absent because the controller requests straight travel; neutral context only, unselected.',
       'variable_assignments':values(1.75,'through'),'unresolved_judgment_calls':[],
       'recording_description':recording}]
    for suffix,exit_x,target_type in (('witness_1',1.75,'compliant_attempt'),
                                        ('witness_2',-1.75,'violating_attempt')):
        cases.append({'case_id':AID+'__'+suffix,'target_law_id':LAW['id'],
           'target_type':target_type,
           'rationale':'Compare requested full-body destination exit on opposite sides of the centerline; outcome awaits measured Native evidence and independent review.',
           'variable_assignments':values(exit_x,'left_turn'),
           'unresolved_judgment_calls':[],
           'paired_probe_id':AID+'__exit_pair',
           'deliberate_differences':['commanded_destination_exit_x_m'],
           'probe':{'primary_variable':'commanded_destination_exit_x_m',
                    'comparison_or_standard':'right versus left of destination centerline at complete exit',
                    'target_value_or_branch':exit_x},
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

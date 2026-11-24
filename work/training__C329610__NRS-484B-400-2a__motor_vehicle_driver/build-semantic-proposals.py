"""Build source-grounded, unselected semantic stage drafts for C329610 2a."""
import hashlib
import json
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
ROOT=FOLDER.parents[1]
ASSIGNMENT=json.loads((ROOT/'inputs'/FOLDER.name/'assignment.json').read_text())
LAW=ASSIGNMENT['law']
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
    judgments=[
      {'phrase':'approach for a left turn',
       'note':'Retain intended route, original full-body positions and entry bracket; the legal start of approach remains for independent review.'},
      {'phrase':'nearest the centerline thereof',
       'note':'Retain full right-half geometry and raw lateral offsets without a numeric legal cutoff.'}]
    template={'template_id':TEMPLATE_ID,'law_id':LAW['id'],'actor':ASSIGNMENT['actor'],
      'quote':LAW['text'],'status':'draft',
      'structure':{'law_id':LAW['id'],
       'activation':{'condition':'driver intends a left turn at an intersection of two two-directional highways',
                     'numeric_conditions':[]},
       'obligation':{'description':'approach in the portion of the right half nearest the centerline of the approached highway',
                     'type':'must','numeric_conditions':[]},
       'exceptions':[],
       'timing':{'description':'approach before first intersection entry','numeric_conditions':[]},
       'judgment_calls_needed':judgments},
      'parameter_refs':parameters}
    r3=write(proposal_dir/'template.json',template)
    observable_refs=[]
    for index, judgment in enumerate(judgments):
        channel='native_body_pose_control' if index==0 else 'st.centre_line'
        observation={'template_id':TEMPLATE_ID,'phrase':judgment['phrase'],
          'note':judgment['note'],'status':'draft',
          'observable_requirements':{
            'observables':[{'name':channel,'unit':'structured',
              'description':'Original time-indexed Native body and surveyed roadway geometry for independent review.'}],
            'context_inputs':[{'name':'surveyed_two_way_intersection','unit':'structured',
              'description':'Original map readback, direction and approach boundaries.'}],
            'sweep_dimensions':[],'landmarks':[],
            'recording_needs':[{'name':channel,'unit':'structured',
              'description':'Retain source-bound frames and body/centerline geometry.'}],
            'limitations':[judgment['note'],'No synthetic diagnostic establishes legal extent.']}}
        observable_refs.append(write(proposal_dir/f'judgment_observables_{index}.json',observation))
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
       'variable_assignments':values(1.75,'through'),'unresolved_judgment_calls':[j['phrase'] for j in judgments],
       'recording_description':recording}]
    for suffix,lateral,target_type in (('controlled_1',1.75,'judgment_sweep'),
                                        ('controlled_2',5.25,'judgment_sweep')):
        cases.append({'case_id':AID+'__'+suffix,'target_law_id':LAW['id'],
           'target_type':target_type,
           'rationale':'Compare requested inner versus outer approach placement in the same right half; outcome awaits measured Native evidence and independent review.',
           'variable_assignments':values(lateral,'left_turn'),
           'unresolved_judgment_calls':[j['phrase'] for j in judgments],
           'paired_probe_id':AID+'__approach_pair',
           'sweep_id':AID+'__raw_approach_geometry',
           'deliberate_differences':['commanded_approach_lateral_m'],
           'probe':{'primary_variable':'commanded_approach_lateral_m',
                    'comparison_or_standard':'inner versus outer approach position within the right half',
                    'target_value_or_branch':lateral},
           'recording_description':recording})
    sweep={'sweep_id':AID+'__raw_approach_geometry','target_law_id':LAW['id'],
           'status':'incomplete','judgment_refs':judgments,
           'rationale':'Two raw offset constructions are CPU prepared; the legal approach start and nearest extent remain for original-source review.',
           'missing_inputs':['Original Native body and roadway readback',
                             'Independent legal judgment of approach extent and nearest position']}
    case_proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],
                   'status':'draft','cases':cases,'sweeps_expanded':True,'sweep_specs':[sweep]}
    r5=write(proposal_dir/'cases.json',case_proposal)
    index={'format':'worker-semantic-delivery','assignment_id':AID,
           'stages':{'relevance_batch':r1,'relevance':r2,'template':r3,
                     'judgment_observables':observable_refs,'bindings':r4,'cases':r5}}
    write(proposal_dir/'semantic-index.json',index)
    print(json.dumps({'semantic_stages':5+len(judgments),'selected_case_drafts':2,
                      'baseline_unselected':1,'judgment_phrases':len(judgments)}))


if __name__=='__main__':main()

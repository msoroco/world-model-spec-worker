"""Author source-bound canonical proposals for the exact C10808 pair."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
PROPOSALS=ROOT/'proposals'


def write(name,value):
    path=PROPOSALS/name
    path.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':'proposals/'+name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    law=ASSIGNMENT['law']
    quote=law['text']
    law_id=ASSIGNMENT['law_id']
    actor=ASSIGNMENT['actor']
    cell=ASSIGNMENT['cell_id']
    cases=json.loads((PROPOSALS/'cases.json').read_text())
    selected=[c for c in cases['cases'] if c['case_id'].endswith(('__dismount_before_uturn','__mounted_uturn'))]
    if len(selected)!=2:
        raise ValueError('Exact case pair missing')
    for case in selected:
        dismount=case['case_id'].endswith('__dismount_before_uturn')
        case.update(target_type='compliant_attempt' if dismount else 'violating_attempt',
            rationale='Planned physical exception comparison; authorization and pedestrian duties remain source-review inputs, with no legal verdict.',
            paired_probe_id='uturn_dismount_exception',
            deliberate_differences=['dismount_before_turn'],
            probe={'primary_variable':'dismount_before_turn',
                'comparison_or_standard':'Dismount exception at the same prohibited-turn sign',
                'target_value_or_branch':'dismount_before_uturn' if dismount else 'mounted_uturn'},
            variable_assignments={'dismount_before_turn':{'kind':'controller','value':dismount}},
            unresolved_judgment_calls=[])
    baseline=dict(selected[0],case_id=ROOT.name+'__baseline',target_law_id=None,
        target_type='baseline',purpose='Shared alley and prohibited-turn sign setup',
        rationale='Shared physical setup; no legal verdict.')
    for key in ('paired_probe_id','deliberate_differences','probe'):
        baseline.pop(key,None)
    cases.update(status='draft',cases=[baseline]+selected,sweep_specs=[],sweeps_expanded=False)
    refs={}
    relevance={'cell_id':cell,'actor':actor,'status':'draft','relevant_laws':[
        {'law_id':law_id,'quote':quote,'applies_to':[actor],
         'relevance_type':'direct restricted U-turn rule and dismount exception',
         'confidence':'high',
         'notes':'Exact alley U-turn branch selects this operator and law; sign authorization and pedestrian duties require source review.'}],
        'borderline_excluded':[]}
    for name in ('relevance_batch','relevance'):
        refs[name]=write(name+'.json',relevance)
    clause='except where such person dismounts from the bicycle, electric bicycle, or electric scooter to make any such turn, in which event such person shall then obey the regulations applicable to pedestrians.'
    if clause not in quote:
        raise ValueError('Exception clause differs from frozen law')
    template={'template_id':law_id+'@'+actor,'law_id':law_id,'actor':actor,'quote':quote,
        'structure':{'law_id':law_id,
            'activation':{'condition':'An authorized no-U-turn sign is erected for a bicycle, electric bicycle, or electric scooter operator.','numeric_conditions':[]},
            'obligation':{'description':'The operator must follow the direction of the no-U-turn sign unless the exact dismount exception applies.','type':'must','numeric_conditions':[]},
            'exceptions':[{'source_clause':clause,'description':'Dismount to make the turn; then obey regulations applicable to pedestrians. Authorization and those regulations need source review.'}],
            'timing':{'description':'Record sign approach, dismount, U-turn and subsequent pedestrian movement in source time order.','numeric_conditions':[]},
            'judgment_calls_needed':[]},
        'parameter_refs':[{'name':'dismount_before_turn','kind':'controller','range_or_domain':'true or false planned controller branch; actual body contact is source-observed'}]}
    refs['template']=write('template.json',template)
    refs['judgment_observables']=[]
    binding={'cell_id':cell,'actor':actor,'status':'draft',
        'established_contexts':['alley','U-turn','turn prohibition device'],
        'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],
        'context_refs':[],'fixed_parameters':[],
        'variable_parameters':[{'name':'dismount_before_turn','kind':'controller',
            'range_or_domain':'true or false planned controller branch; actual body contact is source-observed',
            'used_by_laws':[law_id]}]}
    refs['bindings']=write('bindings.json',binding)
    refs['cases']=write('cases.json',cases)
    write('semantic-index.json',{'format':'worker-semantic-delivery',
        'assignment_id':ASSIGNMENT['assignment_id'],'stages':refs})


if __name__=='__main__':main()

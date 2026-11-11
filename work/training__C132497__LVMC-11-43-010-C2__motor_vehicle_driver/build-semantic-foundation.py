"""Build source-backed draft stages for the conditional right-exit cases."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    target = ROOT/'proposals'/(name+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(value,indent=2)+'\n')
    return {'path':target.relative_to(ROOT).as_posix(),'sha256':sha(target)}


def main():
    source = REPO/'inputs'/ROOT.name/'assignment.json'
    assignment = json.loads(source.read_text())
    law = assignment['law_record']
    law_id,cell_id,actor = (assignment[k] for k in ('law_id','cell_id','actor'))
    request = {'cell':assignment['cell'],'actor':actor}
    common = {'request':request,'law_records':{law_id:law},'dependencies':[]}
    relevance = {'cell_id':cell_id,'actor':actor,'status':'draft',
        'relevant_laws':[{'law_id':law_id,'quote':law['text'],'applies_to':[actor],
            'relevance_type':'specific_match','confidence':'medium',
            'notes':'The cell and law concern a right exit from a roundabout; actual governed lane and exit remain source-review conditions.'}],
        'borderline_excluded':[]}
    stages.validate('relevance_batch',relevance,common)
    stages.validate('relevance',relevance,common)
    refs = {'relevance_batch':write('relevance_batch',relevance),
            'relevance':write('relevance',relevance)}
    template = {'template_id':law_id+'@'+actor,'law_id':law_id,'actor':actor,
        'status':'draft','quote':law['text'],
        'structure':{'activation':{'context':'operation within a roundabout',
            'subject':'operator of a vehicle intending to exit the roundabout'},
            'obligation':{'type':'must','action':'use the right lane to turn right',
                'source_clause':'Shall use the right lane to turn right.'},
            'exceptions':[],
            'timing':{'description':'while turning right to leave the roundabout',
                'numeric_conditions':[]},
            'judgment_calls_needed':[]},
        'parameter_refs':[
            {'name':'roundabout_geometry','kind':'world_setup','range_or_domain':'source-verified two-lane circulation and exit'},
            {'name':'ego_trajectory','kind':'subject_behavior','range_or_domain':'retained original frame-joined pose and lane history'},
            {'name':'commanded_circulating_lane_id','kind':'controller','range_or_domain':'predeclared -2 right or -1 adjacent lane'},
            {'name':'commanded_turn_path','kind':'controller','range_or_domain':'predeclared right-exit path'}]}
    rules = json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
    stages.validate('template',template,{'request':{'law_id':law_id,'actor':actor},
        'law_record':law,'canonical_parameter_rules':rules,'dependencies':[]})
    refs['template'] = write('template',template)
    # Lane side is a measured source relation. The law supplies no qualitative
    # threshold for a separate judgment sweep.
    refs['judgment_observables'] = []
    binding = {'cell_id':cell_id,'actor':actor,'status':'draft',
        'established_contexts':[{'name':'multilane_roundabout_right_turn','source':'frozen catalog cell'}],
        'law_refs':[{'template_id':template['template_id'],'binding_kind':'direct'}],
        'context_refs':[], 'fixed_parameters':[],
        'variable_parameters':[
            {'name':'roundabout_geometry','kind':'world_setup','range_or_domain':'two-lane roundabout with right exit','used_by_laws':[law_id]},
            {'name':'ego_trajectory','kind':'subject_behavior','range_or_domain':'observed original pose and lane history','used_by_laws':[law_id]},
            {'name':'commanded_circulating_lane_id','kind':'controller','range_or_domain':'-2 right or -1 adjacent circulating lane','used_by_laws':[law_id]},
            {'name':'commanded_turn_path','kind':'controller','range_or_domain':'right exit from assigned circulating lane','used_by_laws':[law_id]}]}
    stages.validate('bindings',binding,{'request':dict(request,template_ids=[template['template_id']]),
        'canonical_parameter_rules':rules,'dependencies':[template]})
    refs['bindings'] = write('bindings',binding)
    proof = {'format':'c132497-semantic-foundation-v1','assignment_id':ROOT.name,
             'assignment_sha256':sha(source),'references':refs,
             'stages_validated':['relevance_batch','relevance','template','bindings'],
             'cases_stage_validated':False,'original_native_observed':False,
             'legal_verdict':None}
    write('semantic-foundation-proof',proof)
    print(json.dumps({'validated':4,'proof_sha256':sha(ROOT/'proposals/semantic-foundation-proof.json')}))


if __name__=='__main__':
    main()

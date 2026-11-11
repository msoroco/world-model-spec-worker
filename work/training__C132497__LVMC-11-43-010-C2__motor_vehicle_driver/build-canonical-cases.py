"""Complete the C132497 draft cases stage and bind it to selected constructions."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(name):
    return json.loads((ROOT/'proposals'/(name+'.json')).read_text())


def main():
    assignment = json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
    binding,template = load('bindings'),load('template')
    manifest = json.loads((ROOT/'execution-manifest.json').read_text())
    rows=[]
    for name,lane,target in (('baseline',-2,'baseline'),
                             ('reference',-2,'compliant_attempt'),
                             ('contrast',-1,'violating_attempt')):
        ident = ROOT.name+'__'+name
        selected = next((e for e in manifest['cases'] if e['case_id']==ident),None)
        description = (json.loads((ROOT/selected['construction']).read_text())['recording_description']
                       if selected else json.loads((ROOT/manifest['cases'][0]['construction']).read_text())['recording_description'])
        assignments = {
            'roundabout_geometry':{'kind':'world_setup','value':'source-hashed two-lane counterclockwise right-exit loop','unit':'structured'},
            'ego_trajectory':{'kind':'subject_behavior','value':None,'unit':'structured'},
            'commanded_circulating_lane_id':{'kind':'controller','value':lane,'unit':'index'},
            'commanded_turn_path':{'kind':'controller','value':'road 20 to 21 to right exit 22','unit':'structured'}}
        row={'case_id':ident,'target_law_id':None if target=='baseline' else assignment['law_id'],
             'target_type':target,'rationale':('Shared neutral source context; no accepted original is claimed.'
                if target=='baseline' else 'Conditional right-exit attempt; actual lane and exit require original Native review.'),
             'variable_assignments':assignments,'unresolved_judgment_calls':[],
             'recording_description':description}
        if target!='baseline':
            row.update({'paired_probe_id':ROOT.name+'__right_exit_lane_pair',
                'deliberate_differences':['commanded_circulating_lane_id'],
                'probe':{'primary_variable':'commanded_circulating_lane_id',
                    'comparison_or_standard':'right circulating lane versus adjacent lane for the same intended right exit',
                    'target_value_or_branch':lane}})
        rows.append(row)
    cases={'cell_id':assignment['cell_id'],'actor':assignment['actor'],'status':'draft',
           'sweep_specs':[],'cases':rows}
    rules=json.loads((stages.ROOT/'data/canonical_parameter_aliases.json').read_text())
    request={'cell':assignment['cell'],'actor':assignment['actor']}
    stages.validate('cases',cases,{'request':request,'dependencies':[binding],
        'templates':[template],'canonical_parameter_rules':rules,
        'judgment_completion_policy':{}})
    target=ROOT/'proposals/cases.json'
    target.write_text(json.dumps(cases,indent=2)+'\n')
    refs={name:{'path':'proposals/'+name+'.json','sha256':sha(ROOT/'proposals'/(name+'.json'))}
          for name in ('relevance_batch','relevance','template','bindings','cases')}
    refs['judgment_observables']=[]
    index={'format':'worker-semantic-delivery','assignment_id':ROOT.name,'stages':refs,
           'status':'draft','original_native_observed':False}
    target=ROOT/'proposals/semantic-index.json'
    target.write_text(json.dumps(index,indent=2)+'\n')
    print(json.dumps({'cases_validated':len(rows),'selected_cases':2,
                      'semantic_index_sha256':sha(target)}))


if __name__=='__main__':
    main()

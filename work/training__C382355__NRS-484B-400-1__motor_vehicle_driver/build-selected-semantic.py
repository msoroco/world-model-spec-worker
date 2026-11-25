"""Bind the two 400(1) lane alternatives to the six canonical draft stages."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PROPOSALS=HERE/'proposals'
CASES=('witness_1','witness_2','extreme_right_1','extreme_right_2')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def main():
    assignment=json.loads((HERE.parents[1]/'inputs'/HERE.name/'assignment.json').read_text())
    quote=assignment['law']['text']
    assert 'if the highway has a right turn lane' in quote
    assert 'or must be made from the extreme right lane' in quote
    proposal=json.loads((PROPOSALS/'cases.json').read_text())
    proposal['sweeps_expanded']=True
    selected=json.loads((HERE/'selected-probe-manifest.json').read_text())
    ids={entry['case_id'] for entry in selected['cases']}
    assert ids=={HERE.name+'__'+suffix for suffix in CASES}
    original={case['case_id'].rsplit('__',1)[-1]:case for case in proposal['cases']
              if case['case_id'] in ids}
    for suffix in CASES[2:]:
        if HERE.name+'__'+suffix in {case['case_id'] for case in proposal['cases']}:
            continue
        case=copy.deepcopy(original['witness_'+suffix[-1]])
        case['case_id']=HERE.name+'__'+suffix
        case['paired_probe_id']=HERE.name+'__extreme_right_pair'
        case['deliberate_differences']=['commanded_approach_lane_y_m']
        case['rationale']='Alternative extreme-right lane approach and turn when the surveyed highway lacks a qualifying right-only lane; original Native designation and full-body path need review.'
        case['probe']['target_value_or_branch']='extreme-right alternative, '+('rightmost approach' if suffix.endswith('_1') else 'inner-lane approach')
        proposal['cases'].append(case)
    for case in proposal['cases']:
        if case['case_id'] not in ids:continue
        suffix=case['case_id'].rsplit('__',1)[-1]
        entry=next(row for row in selected['cases'] if row['case_id']==case['case_id'])
        construction=json.loads((HERE/entry['construction']).read_text())
        case['recording_description']=construction['recording_description']
        case['source_branch']=('qualifying right-only lane' if suffix.startswith('witness_')
                               else 'alternative extreme-right lane')
    assert {case['case_id'] for case in proposal['cases'] if case['target_law_id']}==ids
    write(PROPOSALS/'cases.json',proposal)
    index=json.loads((PROPOSALS/'semantic-index.json').read_text())
    index['format']='worker-semantic-delivery'
    index.pop('status',None)
    for key,path in [('relevance_batch','relevance-batch.json'),('relevance','relevance.json'),
                     ('template','template.json'),('bindings','bindings.json'),('cases','cases.json')]:
        index['stages'][key]={'path':'proposals/'+path,'sha256':sha(PROPOSALS/path)}
    index['stages']['judgment_observables']=[
        {'path':'proposals/judgment-intends-to-turn.json',
         'sha256':sha(PROPOSALS/'judgment-intends-to-turn.json')}]
    write(PROPOSALS/'semantic-index.json',index)
    print(json.dumps({'selected_cases':len(ids),'stages':len(index['stages']),
                      'semantic_index_sha256':sha(PROPOSALS/'semantic-index.json')}))


if __name__=='__main__':main()

"""Select four conditional CPU delivery requests while preserving draft history."""
from __future__ import annotations
import hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASES=('witness_1','witness_2','exception_1_1','exception_1_2')
CANDIDATES=('primary','fallback1','fallback2','fallback3')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')

def build():
    draft=json.loads((HERE/'draft-execution-manifest.json').read_text())
    law=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())
    review={
        'format':'c111256-conditional-selected-cpu-source-review-v1',
        'assignment_id':HERE.name,'decision':'select_four_conditional_capture_requests_for_cpu_preparation',
        'legal_verdict':None,'original_native_observed':False,
        'sources':[{'path':str(path.relative_to(ROOT)),'sha256':sha(path)} for path in (
            ROOT/'inputs'/HERE.name/'assignment.json',ROOT/'inputs'/HERE.name/'witnesses.json',
            HERE/'case-plan.json',HERE/'statutory-review.json')],
        'exact_target_clause':law['law']['text'],
        'selected_case_ids':[HERE.name+'__'+case for case in CASES],
        'comparison_ids':[r['comparison_id'] for r in json.loads((HERE/'case-plan.json').read_text())['comparisons']],
        'selection_scope':'conditional software delivery preparation for ego-half uncontrolled crosswalk witness and declared exception contrast only',
        'unclaimed_branches':['NRS 484B.287 cited crossing restrictions','NRS 484B.350 school pedestrian lane',
            'opposite-half near-danger alternative','one-way highway-half alternative'],
        'physical_unknowns':['actual official-device absence','actual pedestrian and ego body paths',
            'physical blind-person/white-cane eligibility and pixels','original Native actor/map readback',
            'independent source-bound pixel review'],
        'limitations':['synthetic blind-white-cane declaration is not a physical cane or legal determination',
            'selection is a CPU build decision; no accepted recording or statutory completion is claimed']}
    review_path=HERE/'native/selection-review.json';write(review_path,review)
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
        'runtime_manifest_sha256':draft['runtime_manifest_sha256'],
        'selection_review':{'path':'native/selection-review.json','sha256':sha(review_path)},
        'status':'selected_cpu_preparation_incomplete','cases':[]}
    for case in CASES:
        case_id=HERE.name+'__'+case
        source=next(e for e in draft['cases'] if e['case_id']==case_id)
        entry={k:v for k,v in source.items() if k not in ('kind','construction','construction_sha256','candidates')}
        entry.update(kind='delivery',candidates=[])
        for candidate in CANDIDATES:
            ref=source if candidate=='primary' else next(c for c in source['candidates'] if c['id']==candidate)
            construction=json.loads((HERE/ref['construction']).read_text())
            construction['status']='selected_delivery_preparation_original_unverified'
            for item in construction['files']:
                if item['path']=='config.json':
                    config=json.loads(item['content'])
                    config['status']='selected_delivery_request_original_unverified'
                    config['physical_success_claimed']=False
                    item['content']=json.dumps(config,indent=2)+'\n'
            target=HERE/'selected-candidates'/case/candidate/'construction.json'
            write(target,construction)
            selected={'id':candidate,'construction':str(target.relative_to(HERE)),
                      'construction_sha256':sha(target)}
            if candidate=='primary':
                entry['construction']=selected['construction']
                entry['construction_sha256']=selected['construction_sha256']
            else:
                selected.update(trigger=ref['trigger'],changed_knobs=ref['changed_knobs'])
                entry['candidates'].append(selected)
        manifest['cases'].append(entry)
    path=HERE/'execution-manifest.json';write(path,manifest)
    return {'selected_cases':4,'selected_constructions':16,'manifest_sha256':sha(path)}
if __name__=='__main__':print(json.dumps(build()))

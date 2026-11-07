"""Bind the frozen center-lane clause to both controlled unselected case groups."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LAW='NRS-484B-223-3b'
SUFFIXES=(('witness_1','witness_2'),('numeric_1_0','numeric_1_1','numeric_1_2'))


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen=read(ROOT/'inputs/coverage/branch-sources.json')['laws'][LAW]
    plan=read(HERE/'case-plan.json')
    matrix_path=ROOT/'work/_shared/branch-coverage.json'
    matrix=read(matrix_path)
    review=read(ROOT/'work/_shared/branch-review.json')
    branches=matrix['laws'][LAW]['branches']
    if (frozen['law']['text']!=plan['source_law']['text'] or
        frozen['law']['source']!=plan['source_law']['source'] or
        set(frozen['topics'])!={'text-0','text-1','reviewed-scope-0'} or
        plan['assignment_id']!=HERE.name or len(branches)!=2 or
        review['coverage_sha256']!=sha(matrix_path) or LAW in review['missing_branches']):
        raise ValueError('Frozen statutory source or matrix differs')
    cases={c['case_id'] for c in plan['cases']}
    comparisons={c['comparison_id']:c for c in plan['comparisons']}
    if len(cases)!=5 or len(comparisons)!=2:
        raise ValueError('Controlled case inventory differs')
    for branch,suffixes in zip(branches,SUFFIXES):
        expected={HERE.name+'__'+suffix for suffix in suffixes}
        if (branch['status']!='runnable' or branch['assignment_id']!=HERE.name or
            set(branch['topic_ids'])!=set(frozen['topics']) or
            set(branch['case_ids'])!=expected or len(branch['comparison_ids'])!=1 or
            set(comparisons[branch['comparison_ids'][0]]['case_ids'])!=expected):
            raise ValueError('Clause, numeric boundary or controlled comparison differs')
    if cases!=set().union(*(set(branch['case_ids']) for branch in branches)):
        raise ValueError('Controlled cases are not covered by statute branches')
    print(json.dumps({'passed':True,'law_id':LAW,'source_topics':sorted(frozen['topics']),
                      'branches':2,'controlled_cases':5,'comparisons':2,
                      'pending_original_design_and_delivery':True,
                      'selected':False},sort_keys=True))


if __name__=='__main__':main()

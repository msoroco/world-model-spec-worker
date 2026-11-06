"""Independent C329610 NRS 484B.413(2) source/case branch audit."""
import hashlib
import json
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
AID='training__C329610__NRS-484B-413-2__motor_vehicle_driver'
LAW='NRS-484B-413-2'


def main():
    matrix_path=REPO/'work/_shared/branch-coverage.json'
    matrix=json.loads(matrix_path.read_text())
    review=json.loads((REPO/'work/_shared/branch-review.json').read_text())
    source=json.loads((REPO/'inputs/coverage/branch-sources.json').read_text())['laws'][LAW]
    plan=json.loads((REPO/'work'/AID/'case-plan.json').read_text())
    assert review['coverage_sha256']==hashlib.sha256(matrix_path.read_bytes()).hexdigest()
    assert LAW in review['missing_branches']  # C104393 source inventory remains unresolved.
    branches=[b for b in matrix['laws'][LAW]['branches'] if b.get('assignment_id')==AID]
    assert len(branches)==2 and all(b['status']=='pending_review' for b in branches)
    assert set().union(*(set(b['topic_ids']) for b in branches))==set(source['topics'])
    cases={c['case_id']:c for c in plan['cases']}
    comparisons={c['comparison_id']:c for c in plan['comparisons']}
    assert len(cases)==6 and len(comparisons)==2
    bound=set()
    for branch in branches:
        selected=set(branch['case_ids'])
        assert len(selected)==3 and selected<=set(cases)
        assert len(branch['comparison_ids'])==1
        assert selected==set(comparisons[branch['comparison_ids'][0]]['case_ids'])
        assert len({cases[case]['area_classification'] for case in selected})==1
        assert sorted(cases[case]['requested_setting'] for case in selected) in ([90,100,110],[290,300,310])
        bound|=selected
    assert bound==set(cases)
    print(json.dumps({'source_topics':len(source['topics']),'planned_cases':6,
                      'controlled_comparisons':2,'pending_c329610_branches':2,
                      'runnable_branches':0,'c104393_inventory_pending':True}))


if __name__=='__main__':main()
